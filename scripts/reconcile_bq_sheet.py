#!/usr/bin/env python3
"""
scripts/reconcile_bq_sheet.py

Deterministic Reconciliation Engine between BigQuery and Google Sheets (OPTION_SHEET).
Provides key-based deterministic comparison (MATCH, BQ_ONLY, SHEET_ONLY,
VALUE_MISMATCH, TIMESTAMP_MISMATCH) using stable keys:
- timestamp / snapshot ID
- symbol
- expiry
- strike
- side / contract

Enforces authoritativeness rules: neither system blindly overwrites the other.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple


def normalize_symbol(sym: Any) -> str:
    """Normalize symbol string."""
    if sym is None:
        return ""
    return str(sym).strip().upper()


def normalize_price(val: Any) -> Optional[float]:
    """Parse numeric price safely, stripping commas and currency formatting."""
    if val is None or val == "":
        return None
    try:
        clean_str = str(val).replace(",", "").replace("₹", "").strip()
        f = float(clean_str)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def parse_timestamp(val: Any) -> Optional[datetime]:
    """Parse various timestamp formats into timezone-aware UTC datetime."""
    if not val or not str(val).strip():
        return None
    val_str = str(val).strip()

    # 1. ISO 8601 with offset
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S.%f%z",
    ]:
        try:
            return datetime.strptime(val_str, fmt).astimezone(timezone.utc)
        except ValueError:
            pass

    # 2. Naive string assumed IST if ending in IST or standard engine timestamp
    clean_val = val_str.replace(" IST", "").strip()
    for fmt in [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]:
        try:
            dt = datetime.strptime(clean_val, fmt)
            ist_offset = timezone(timedelta(hours=5, minutes=30))
            return dt.replace(tzinfo=ist_offset).astimezone(timezone.utc)
        except ValueError:
            pass

    return None


def extract_snapshot_id(val: Any) -> str:
    """Extract canonical UTC minute bucket (e.g. 2026-10-01T11:45Z) from timestamp."""
    dt = parse_timestamp(val)
    if dt:
        return dt.strftime("%Y-%m-%dT%H:%MZ")
    if val:
        return str(val).strip()[:16]
    return "UNKNOWN_SNAPSHOT"


def explode_option_contracts(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Explodes wide option snapshot rows or single contract rows into individual option contracts.
    Yields normalized contract dicts with:
    snapshot_id, symbol, expiry, strike, side, contract, price, oi, chg_pct, raw_timestamp.
    """
    contracts = []
    for r in records:
        sym = normalize_symbol(r.get("symbol"))
        raw_ts = (
            r.get("snapshot_timestamp")
            or r.get("timestamp_ist")
            or r.get("predicted_at_ist")
            or r.get("timestamp")
        )
        snap_id = extract_snapshot_id(raw_ts)
        expiry = str(r.get("expiry") or r.get("nearest_expiry") or r.get("target_date") or "").strip().upper()
        raw_strike = r.get("atm_strike") or r.get("strike") or r.get("target_strike")
        strike_num = normalize_price(raw_strike)
        strike_str = str(int(round(strike_num))) if strike_num is not None else str(raw_strike or "").strip()

        # Case A: Explicit single contract (has side / option_type / contract_symbol)
        if "side" in r or "option_type" in r or "contract_symbol" in r:
            side = str(r.get("side") or r.get("option_type") or "").strip().upper()
            contract = str(r.get("contract_symbol") or r.get("contract") or "").strip().upper()
            price = normalize_price(r.get("entry_ltp") or r.get("ltp") or r.get("price"))
            contracts.append({
                "snapshot_id": snap_id,
                "symbol": sym,
                "expiry": expiry,
                "strike": strike_str,
                "side": side,
                "contract": contract or f"{sym}{expiry}{strike_str}{side}",
                "price": price,
                "oi": normalize_price(r.get("oi")),
                "chg_pct": normalize_price(r.get("chg_pct")),
                "action": r.get("action_rating") or r.get("forensic_action_signal"),
                "raw_timestamp": raw_ts,
            })
            continue

        # Case B: Wide row with both CE & PE contracts (e.g. FORENSIC_LIVE, option_predictions_live)
        # CE contract
        ce_price = normalize_price(r.get("ce_ltp"))
        ce_contract = str(r.get("atm_ce_contract") or r.get("ce_contract") or "").strip().upper()
        if not ce_contract and sym and strike_str:
            ce_contract = f"{sym}{expiry}{strike_str}CE"
        contracts.append({
            "snapshot_id": snap_id,
            "symbol": sym,
            "expiry": expiry,
            "strike": strike_str,
            "side": "CE",
            "contract": ce_contract,
            "price": ce_price,
            "oi": normalize_price(r.get("ce_oi")),
            "chg_pct": normalize_price(r.get("ce_chg_pct")),
            "action": r.get("action_rating") or r.get("forensic_action_signal"),
            "raw_timestamp": raw_ts,
        })

        # PE contract
        pe_price = normalize_price(r.get("pe_ltp"))
        pe_contract = str(r.get("atm_pe_contract") or r.get("pe_contract") or "").strip().upper()
        if not pe_contract and sym and strike_str:
            pe_contract = f"{sym}{expiry}{strike_str}PE"
        contracts.append({
            "snapshot_id": snap_id,
            "symbol": sym,
            "expiry": expiry,
            "strike": strike_str,
            "side": "PE",
            "contract": pe_contract,
            "price": pe_price,
            "oi": normalize_price(r.get("pe_oi")),
            "chg_pct": normalize_price(r.get("pe_chg_pct")),
            "action": r.get("action_rating") or r.get("forensic_action_signal"),
            "raw_timestamp": raw_ts,
        })

    return contracts


def reconcile_contract_level(
    bq_contracts: List[Dict[str, Any]],
    sheet_contracts: List[Dict[str, Any]],
    price_tol_pct: float = 0.5,
    time_tol_sec: float = 300.0,
) -> Dict[str, Any]:
    """
    Deterministically reconciles option contracts using exact stable composite keys:
    - timestamp/snapshot ID
    - symbol
    - expiry
    - strike
    - side/contract
    """
    def make_key(c: Dict[str, Any]) -> str:
        return (
            f"{c.get('snapshot_id')}::"
            f"{c.get('symbol')}::"
            f"{c.get('expiry')}::"
            f"{c.get('strike')}::"
            f"{c.get('side')}::"
            f"{c.get('contract')}"
        )

    # Fallback key without snapshot_id to diagnose pure timestamp drift
    def make_contract_id(c: Dict[str, Any]) -> str:
        return (
            f"{c.get('symbol')}::"
            f"{c.get('expiry')}::"
            f"{c.get('strike')}::"
            f"{c.get('side')}"
        )

    bq_map = {make_key(c): c for c in bq_contracts if c.get("symbol")}
    sheet_map = {make_key(c): c for c in sheet_contracts if c.get("symbol")}

    bq_contract_index = {make_contract_id(c): c for c in bq_contracts if c.get("symbol")}
    sheet_contract_index = {make_contract_id(c): c for c in sheet_contracts if c.get("symbol")}

    all_keys = sorted(set(bq_map.keys()) | set(sheet_map.keys()))

    details: List[Dict[str, Any]] = []
    counts = {
        "MATCH": 0,
        "BQ_ONLY": 0,
        "SHEET_ONLY": 0,
        "VALUE_MISMATCH": 0,
        "TIMESTAMP_MISMATCH": 0,
    }

    for k in all_keys:
        in_bq = k in bq_map
        in_sheet = k in sheet_map

        if in_bq and not in_sheet:
            bq_c = bq_map[k]
            cid = make_contract_id(bq_c)
            # Check if present in Sheet under different snapshot_id (pure timestamp mismatch)
            if cid in sheet_contract_index:
                sh_c = sheet_contract_index[cid]
                bq_ts = parse_timestamp(bq_c.get("raw_timestamp"))
                sh_ts = parse_timestamp(sh_c.get("raw_timestamp"))
                sec_diff = abs((bq_ts - sh_ts).total_seconds()) if bq_ts and sh_ts else 999999
                counts["TIMESTAMP_MISMATCH"] += 1
                details.append({
                    "composite_key": k,
                    "snapshot_id": bq_c.get("snapshot_id"),
                    "symbol": bq_c.get("symbol"),
                    "expiry": bq_c.get("expiry"),
                    "strike": bq_c.get("strike"),
                    "side": bq_c.get("side"),
                    "contract": bq_c.get("contract"),
                    "status": "TIMESTAMP_MISMATCH",
                    "in_bq": True,
                    "in_sheet": True,
                    "bq_price": bq_c.get("price"),
                    "sheet_price": sh_c.get("price"),
                    "bq_timestamp": bq_c.get("raw_timestamp"),
                    "sheet_timestamp": sh_c.get("raw_timestamp"),
                    "notes": f"Contract matches across systems but snapshot times differ by {round(sec_diff, 1)}s (BQ={bq_c.get('snapshot_id')} vs Sheet={sh_c.get('snapshot_id')}).",
                })
            else:
                counts["BQ_ONLY"] += 1
                details.append({
                    "composite_key": k,
                    "snapshot_id": bq_c.get("snapshot_id"),
                    "symbol": bq_c.get("symbol"),
                    "expiry": bq_c.get("expiry"),
                    "strike": bq_c.get("strike"),
                    "side": bq_c.get("side"),
                    "contract": bq_c.get("contract"),
                    "status": "BQ_ONLY",
                    "in_bq": True,
                    "in_sheet": False,
                    "bq_price": bq_c.get("price"),
                    "sheet_price": None,
                    "bq_timestamp": bq_c.get("raw_timestamp"),
                    "sheet_timestamp": None,
                    "notes": "Option contract present in BigQuery snapshot but completely missing from Google Sheet tab.",
                })
        elif in_sheet and not in_bq:
            sh_c = sheet_map[k]
            cid = make_contract_id(sh_c)
            if cid in bq_contract_index:
                # Already processed under TIMESTAMP_MISMATCH during BQ evaluation
                pass
            else:
                counts["SHEET_ONLY"] += 1
                details.append({
                    "composite_key": k,
                    "snapshot_id": sh_c.get("snapshot_id"),
                    "symbol": sh_c.get("symbol"),
                    "expiry": sh_c.get("expiry"),
                    "strike": sh_c.get("strike"),
                    "side": sh_c.get("side"),
                    "contract": sh_c.get("contract"),
                    "status": "SHEET_ONLY",
                    "in_bq": False,
                    "in_sheet": True,
                    "bq_price": None,
                    "sheet_price": sh_c.get("price"),
                    "bq_timestamp": None,
                    "sheet_timestamp": sh_c.get("raw_timestamp"),
                    "notes": "Option contract present in Google Sheet tab but completely missing from BigQuery snapshot.",
                })
        else:
            bq_c = bq_map[k]
            sh_c = sheet_map[k]

            bq_price = bq_c.get("price")
            sh_price = sh_c.get("price")

            bq_ts = parse_timestamp(bq_c.get("raw_timestamp"))
            sh_ts = parse_timestamp(sh_c.get("raw_timestamp"))

            price_mismatch = False
            if bq_price is not None and sh_price is not None and bq_price > 0:
                pct_diff = abs(bq_price - sh_price) / bq_price * 100.0
                if pct_diff > price_tol_pct:
                    price_mismatch = True

            time_mismatch = False
            if bq_ts is not None and sh_ts is not None:
                sec_diff = abs((bq_ts - sh_ts).total_seconds())
                if sec_diff > time_tol_sec:
                    time_mismatch = True

            if price_mismatch:
                status = "VALUE_MISMATCH"
                counts["VALUE_MISMATCH"] += 1
                notes = f"Option premium mismatch: BQ={bq_price}, Sheet={sh_price} (pct_diff > {price_tol_pct}%)."
            elif time_mismatch:
                status = "TIMESTAMP_MISMATCH"
                counts["TIMESTAMP_MISMATCH"] += 1
                notes = f"Option timestamp mismatch: BQ={bq_ts.isoformat()}, Sheet={sh_ts.isoformat()} (sec_diff > {time_tol_sec}s)."
            else:
                status = "MATCH"
                counts["MATCH"] += 1
                notes = "Exact contract stable keys, option prices, and timestamps match across both layers."

            details.append({
                "composite_key": k,
                "snapshot_id": bq_c.get("snapshot_id"),
                "symbol": bq_c.get("symbol"),
                "expiry": bq_c.get("expiry"),
                "strike": bq_c.get("strike"),
                "side": bq_c.get("side"),
                "contract": bq_c.get("contract"),
                "status": status,
                "in_bq": True,
                "in_sheet": True,
                "bq_price": bq_price,
                "sheet_price": sh_price,
                "bq_timestamp": bq_c.get("raw_timestamp"),
                "sheet_timestamp": sh_c.get("raw_timestamp"),
                "notes": notes,
            })

    total_keys = len(details)
    match_pct = (counts["MATCH"] / total_keys * 100.0) if total_keys > 0 else 0.0

    return {
        "summary": {
            "total_keys_evaluated": total_keys,
            "match_count": counts["MATCH"],
            "match_pct": round(match_pct, 2),
            "bq_only_count": counts["BQ_ONLY"],
            "sheet_only_count": counts["SHEET_ONLY"],
            "value_mismatch_count": counts["VALUE_MISMATCH"],
            "timestamp_mismatch_count": counts["TIMESTAMP_MISMATCH"],
        },
        "authoritativeness": {
            "primary_producer": "angel_prediction_engine.py (in-memory pipeline)",
            "producer_source": "Angel One SmartAPI Full Market Feed (219 F&O symbols)",
            "bq_sink": "fno_predictions.option_predictions_live (WRITE_TRUNCATE)",
            "sheet_sink": "OPTION_SHEET.FORENSIC_LIVE (ws_fl.update)",
            "reconciliation_rule": (
                "Neither BigQuery nor OPTION_SHEET is authoritative over the other; "
                "both are downstream presentation/storage layers populated concurrently. "
                "Discrepancies indicate execution failure or network timeout during one sink write. "
                "Never overwrite one from the other without confirming upstream origin."
            ),
        },
        "details": details,
    }


def reconcile_records(
    bq_records: List[Dict[str, Any]],
    sheet_records: List[Dict[str, Any]],
    key_fields: Tuple[str, ...] = ("symbol",),
    price_tol_pct: float = 0.5,
    time_tol_sec: float = 300.0,
) -> Dict[str, Any]:
    """Underlying-level reconciliation."""
    def make_key(rec: Dict[str, Any]) -> str:
        parts = [normalize_symbol(rec.get(k, "")) for k in key_fields]
        return "::".join(parts)

    bq_map = {make_key(r): r for r in bq_records if make_key(r)}
    sheet_map = {make_key(r): r for r in sheet_records if make_key(r)}

    all_keys = sorted(set(bq_map.keys()) | set(sheet_map.keys()))

    details: List[Dict[str, Any]] = []
    counts = {
        "MATCH": 0,
        "BQ_ONLY": 0,
        "SHEET_ONLY": 0,
        "VALUE_MISMATCH": 0,
        "TIMESTAMP_MISMATCH": 0,
    }

    for k in all_keys:
        in_bq = k in bq_map
        in_sheet = k in sheet_map

        if in_bq and not in_sheet:
            status = "BQ_ONLY"
            counts["BQ_ONLY"] += 1
            bq_r = bq_map[k]
            details.append({
                "key": k,
                "symbol": bq_r.get("symbol", k),
                "status": status,
                "in_bq": True,
                "in_sheet": False,
                "bq_price": bq_r.get("spot_ltp"),
                "sheet_price": None,
                "bq_action": bq_r.get("action_rating"),
                "sheet_action": None,
                "bq_timestamp": bq_r.get("snapshot_timestamp"),
                "sheet_timestamp": None,
                "notes": "Record found in BigQuery snapshot but missing in Google Sheet tab.",
            })
        elif in_sheet and not in_bq:
            status = "SHEET_ONLY"
            counts["SHEET_ONLY"] += 1
            sh_r = sheet_map[k]
            details.append({
                "key": k,
                "symbol": sh_r.get("symbol", k),
                "status": status,
                "in_bq": False,
                "in_sheet": True,
                "bq_price": None,
                "sheet_price": sh_r.get("spot_ltp") or sh_r.get("fut_ltp"),
                "bq_action": None,
                "sheet_action": sh_r.get("action_rating") or sh_r.get("forensic_action_signal"),
                "bq_timestamp": None,
                "sheet_timestamp": sh_r.get("timestamp_ist"),
                "notes": "Record found in Google Sheet tab but missing in BigQuery snapshot.",
            })
        else:
            bq_r = bq_map[k]
            sh_r = sheet_map[k]

            bq_price = normalize_price(bq_r.get("spot_ltp"))
            sh_price = normalize_price(sh_r.get("spot_ltp") or sh_r.get("fut_ltp"))

            bq_ts = parse_timestamp(bq_r.get("snapshot_timestamp"))
            sh_ts = parse_timestamp(sh_r.get("timestamp_ist") or sh_r.get("timestamp"))

            price_mismatch = False
            if bq_price is not None and sh_price is not None and bq_price > 0:
                pct_diff = abs(bq_price - sh_price) / bq_price * 100.0
                if pct_diff > price_tol_pct:
                    price_mismatch = True

            time_mismatch = False
            if bq_ts is not None and sh_ts is not None:
                sec_diff = abs((bq_ts - sh_ts).total_seconds())
                if sec_diff > time_tol_sec:
                    time_mismatch = True

            if price_mismatch:
                status = "VALUE_MISMATCH"
                counts["VALUE_MISMATCH"] += 1
                notes = f"Price mismatch: BQ={bq_price}, Sheet={sh_price} (diff > {price_tol_pct}%)."
            elif time_mismatch:
                status = "TIMESTAMP_MISMATCH"
                counts["TIMESTAMP_MISMATCH"] += 1
                notes = f"Timestamp mismatch: BQ={bq_ts.isoformat()}, Sheet={sh_ts.isoformat()} (diff > {time_tol_sec}s)."
            else:
                status = "MATCH"
                counts["MATCH"] += 1
                notes = "Exact key and metrics agree across both storage layers."

            details.append({
                "key": k,
                "symbol": bq_r.get("symbol", k),
                "status": status,
                "in_bq": True,
                "in_sheet": True,
                "bq_price": bq_price,
                "sheet_price": sh_price,
                "bq_action": bq_r.get("action_rating"),
                "sheet_action": sh_r.get("action_rating") or sh_r.get("forensic_action_signal"),
                "bq_timestamp": bq_r.get("snapshot_timestamp"),
                "sheet_timestamp": sh_r.get("timestamp_ist") or sh_r.get("timestamp"),
                "notes": notes,
            })

    total_keys = len(all_keys)
    match_pct = (counts["MATCH"] / total_keys * 100.0) if total_keys > 0 else 0.0

    return {
        "summary": {
            "total_keys_evaluated": total_keys,
            "match_count": counts["MATCH"],
            "match_pct": round(match_pct, 2),
            "bq_only_count": counts["BQ_ONLY"],
            "sheet_only_count": counts["SHEET_ONLY"],
            "value_mismatch_count": counts["VALUE_MISMATCH"],
            "timestamp_mismatch_count": counts["TIMESTAMP_MISMATCH"],
        },
        "authoritativeness": {
            "primary_producer": "angel_prediction_engine.py / scanner.py (in-memory pipeline)",
            "producer_source": "Angel One SmartAPI Full Market Feed (219 F&O symbols)",
            "bq_write_path": "sync_to_bigquery() -> WRITE_TRUNCATE into fno_predictions.option_predictions_live",
            "sheet_write_path": "sync_to_google_sheet() -> ws_fl.update() into FORENSIC_LIVE",
            "reconciliation_rule": (
                "Neither BigQuery nor OPTION_SHEET is authoritative over the other; "
                "both are downstream presentation/storage layers populated concurrently. "
                "Discrepancies indicate execution failure or network timeout during one sink write. "
                "Never overwrite one from the other without confirming upstream origin."
            ),
        },
        "details": details,
    }


HEADER_SIGNATURE_TOKENS = {
    "symbol", "sym", "ticker", "ltp", "fut_ltp", "spot_ltp", "strike", "atm_strike",
    "expiry", "nearest_expiry", "side", "contract", "option_contract", "atm_ce_contract",
    "timestamp", "timestamp_ist", "logged_at_ist", "rank", "rank_time_ist", "gate_id",
    "session_date", "metric", "check_id", "news_type", "open", "close"
}


def detect_header_row(raw_rows: List[List[Any]], max_scan: int = 10) -> int:
    """
    Dynamically identifies the header row index (0-indexed) by scoring
    recognized domain keywords across the top rows.
    Leaves title banners, audit notes, and disclaimers intact.
    """
    best_idx = 0
    max_score = -1

    for idx, row in enumerate(raw_rows[:max_scan]):
        if not row:
            continue
        clean_tokens = [
            str(c).strip().lower().replace(" ", "_").replace("(", "").replace(")", "").replace("%", "pct")
            for c in row if c
        ]
        score = sum(1 for tok in clean_tokens if any(sig in tok for sig in HEADER_SIGNATURE_TOKENS))
        # Penalty for title or disclaimer rows with few columns or long single text
        if len(clean_tokens) <= 2:
            score -= 2
        if score > max_score:
            max_score = score
            best_idx = idx

    return best_idx


def load_records_from_csv(file_path: str) -> List[Dict[str, Any]]:
    """Load records from a CSV file with dynamic header discovery and normalization."""
    with open(file_path, "r", encoding="utf-8-sig") as f:
        raw_rows = list(csv.reader(f))
    if not raw_rows:
        return []

    header_idx = detect_header_row(raw_rows)
    raw_headers = raw_rows[header_idx]
    clean_headers = [
        str(h).strip().lower().replace(" ", "_").replace("(", "").replace(")", "").replace("%", "pct")
        for h in raw_headers
    ]

    records = []
    for row in raw_rows[header_idx + 1:]:
        if not any(row):
            continue
        normalized = {}
        for k, v in zip(clean_headers, row):
            if k:
                normalized[k] = v
        if "fut_ltp" in normalized and "spot_ltp" not in normalized:
            normalized["spot_ltp"] = normalized["fut_ltp"]
        if "forensic_action_signal" in normalized and "action_rating" not in normalized:
            normalized["action_rating"] = normalized["forensic_action_signal"]
        records.append(normalized)
    return records


def load_records_from_json(file_path: str) -> List[Dict[str, Any]]:
    """Load records from JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "records" in data:
            return data["records"]
        return [data]


def export_reconciliation_csv(details: List[Dict[str, Any]], out_path: str):
    """Write contract-level or underlying-level reconciliation details to CSV."""
    if not details:
        return
    is_contract = "composite_key" in details[0]
    if is_contract:
        fieldnames = [
            "COMPOSITE_KEY",
            "SNAPSHOT_ID",
            "SYMBOL",
            "EXPIRY",
            "STRIKE",
            "SIDE",
            "CONTRACT",
            "STATUS",
            "IN_BIGQUERY",
            "IN_GOOGLE_SHEET",
            "BQ_PRICE",
            "SHEET_PRICE",
            "BQ_TIMESTAMP",
            "SHEET_TIMESTAMP",
            "RECONCILIATION_NOTES",
        ]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fieldnames)
            for d in details:
                writer.writerow([
                    d.get("composite_key"),
                    d.get("snapshot_id"),
                    d.get("symbol"),
                    d.get("expiry"),
                    d.get("strike"),
                    d.get("side"),
                    d.get("contract"),
                    d.get("status"),
                    "YES" if d.get("in_bq") else "NO",
                    "YES" if d.get("in_sheet") else "NO",
                    d.get("bq_price"),
                    d.get("sheet_price"),
                    d.get("bq_timestamp"),
                    d.get("sheet_timestamp"),
                    d.get("notes"),
                ])
    else:
        fieldnames = [
            "SYMBOL",
            "STATUS",
            "IN_BIGQUERY",
            "IN_GOOGLE_SHEET",
            "BQ_SPOT_LTP",
            "SHEET_FUT_LTP",
            "BQ_ACTION_RATING",
            "SHEET_ACTION_SIGNAL",
            "BQ_SNAPSHOT_TIMESTAMP",
            "SHEET_TIMESTAMP_IST",
            "RECONCILIATION_NOTES",
        ]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fieldnames)
            for d in details:
                writer.writerow([
                    d.get("symbol"),
                    d.get("status"),
                    "YES" if d.get("in_bq") else "NO",
                    "YES" if d.get("in_sheet") else "NO",
                    d.get("bq_price"),
                    d.get("sheet_price"),
                    d.get("bq_action"),
                    d.get("sheet_action"),
                    d.get("bq_timestamp"),
                    d.get("sheet_timestamp"),
                    d.get("notes"),
                ])


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Deterministic BigQuery <-> Google Sheet Reconciliation")
    parser.add_argument("--bq-file", type=str, help="Path to local BigQuery snapshot export (CSV or JSON)")
    parser.add_argument("--sheet-file", type=str, help="Path to local Google Sheet snapshot export (CSV or JSON)")
    parser.add_argument("--mode", type=str, choices=["contract", "underlying"], default="contract", help="Reconciliation level: contract (default) or underlying")
    parser.add_argument("--output-csv", type=str, help="Path to export reconciliation CSV output")
    parser.add_argument("--output-json", type=str, help="Path to export reconciliation JSON output")
    parser.add_argument("--live", action="store_true", help="Fetch live data directly from BigQuery and Google Sheets")
    args = parser.parse_args()

    bq_records = []
    sheet_records = []

    if args.live:
        print("[INFO] Querying live BigQuery and Google Sheets...")
        try:
            from angel_prediction_engine import get_bigquery_client, get_gspread_client, BQ_DATASET_ID, SHEET_ID
            bq_client = get_bigquery_client()
            query = f"SELECT * FROM `{bq_client.project}.{BQ_DATASET_ID}.option_predictions_live`"
            df = bq_client.query(query).to_dataframe()
            bq_records = df.to_dict(orient="records")
            print(f"[OK] Fetched {len(bq_records)} rows from BigQuery option_predictions_live.")

            gc = get_gspread_client()
            sh = gc.open_by_key(SHEET_ID)
            ws = sh.worksheet("FORENSIC_LIVE")
            all_values = ws.get_all_values()
            if len(all_values) > 1:
                header_idx = detect_header_row(all_values)
                headers = [
                    str(h).strip().lower().replace(" ", "_").replace("(", "").replace(")", "").replace("%", "pct")
                    for h in all_values[header_idx]
                ]
                for r in all_values[header_idx + 1:]:
                    if any(r):
                        row_dict = dict(zip(headers, r))
                        sheet_records.append(row_dict)
            print(f"[OK] Fetched {len(sheet_records)} rows from Google Sheet FORENSIC_LIVE.")
        except Exception as e:
            print(f"[ERROR] Live fetch failed: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        if not args.bq_file or not args.sheet_file:
            print("[ERROR] Please provide --live OR both --bq-file and --sheet-file.", file=sys.stderr)
            sys.exit(1)

        if args.bq_file.endswith(".json"):
            bq_records = load_records_from_json(args.bq_file)
        else:
            bq_records = load_records_from_csv(args.bq_file)

        if args.sheet_file.endswith(".json"):
            sheet_records = load_records_from_json(args.sheet_file)
        else:
            sheet_records = load_records_from_csv(args.sheet_file)

    if args.mode == "contract":
        bq_contracts = explode_option_contracts(bq_records)
        sheet_contracts = explode_option_contracts(sheet_records)
        result = reconcile_contract_level(bq_contracts, sheet_contracts)
        level_name = "CONTRACT-LEVEL (SNAPSHOT_ID :: SYMBOL :: EXPIRY :: STRIKE :: SIDE :: CONTRACT)"
    else:
        result = reconcile_records(bq_records, sheet_records)
        level_name = "UNDERLYING-LEVEL (SYMBOL)"

    summary = result["summary"]

    print("\n" + "=" * 70)
    print("  BIGQUERY <-> OPTION_SHEET DETERMINISTIC RECONCILIATION REPORT")
    print("=" * 70)
    print(f"  Level:                   {level_name}")
    print(f"  Total Keys Evaluated:    {summary['total_keys_evaluated']}")
    print(f"  MATCH:                   {summary['match_count']} ({summary['match_pct']}%)")
    print(f"  BQ_ONLY:                 {summary['bq_only_count']}")
    print(f"  SHEET_ONLY:              {summary['sheet_only_count']}")
    print(f"  VALUE_MISMATCH:          {summary['value_mismatch_count']}")
    print(f"  TIMESTAMP_MISMATCH:      {summary['timestamp_mismatch_count']}")
    print("=" * 70)
    print(f"  Authoritative Producer:  {result['authoritativeness']['primary_producer']}")
    print(f"  Rule:                    {result['authoritativeness']['reconciliation_rule']}")
    print("=" * 70 + "\n")

    if args.output_csv:
        export_reconciliation_csv(result["details"], args.output_csv)
        print(f"[OK] Reconciliation CSV saved to: {args.output_csv}")

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"[OK] Reconciliation JSON saved to: {args.output_json}")


if __name__ == "__main__":
    main()

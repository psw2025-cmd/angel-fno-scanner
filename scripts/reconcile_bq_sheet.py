#!/usr/bin/env python3
"""
scripts/reconcile_bq_sheet.py

Deterministic Reconciliation Engine between BigQuery and Google Sheets (OPTION_SHEET).
Provides key-based deterministic comparison (MATCH, BQ_ONLY, SHEET_ONLY,
VALUE_MISMATCH, TIMESTAMP_MISMATCH) and authoritativeness analysis.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from datetime import datetime, timezone
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

    # Common formats
    # 1. ISO 8601 with offset: 2026-10-01T11:45:00+00:00 or 2026-10-01 11:45:00.452891+00:00
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
            # Default naive sheet timestamps from engine to IST (UTC+5:30)
            from datetime import timedelta
            ist_offset = timezone(timedelta(hours=5, minutes=30))
            return dt.replace(tzinfo=ist_offset).astimezone(timezone.utc)
        except ValueError:
            pass

    return None


def reconcile_records(
    bq_records: List[Dict[str, Any]],
    sheet_records: List[Dict[str, Any]],
    key_fields: Tuple[str, ...] = ("symbol",),
    price_tol_pct: float = 0.5,
    time_tol_sec: float = 300.0,
) -> Dict[str, Any]:
    """
    Deterministically reconciles BigQuery records against Google Sheet records.
    
    Returns structured results:
    - summary: counts of MATCH, BQ_ONLY, SHEET_ONLY, VALUE_MISMATCH, TIMESTAMP_MISMATCH
    - details: list of row-by-row reconciliation evaluations
    - authoritativeness: explanation of data provenance
    """
    def make_key(rec: Dict[str, Any]) -> str:
        parts = [normalize_symbol(rec.get(k, "")) for k in key_fields]
        return "::".join(parts)

    bq_map: Dict[str, Dict[str, Any]] = {}
    for r in bq_records:
        k = make_key(r)
        if k:
            bq_map[k] = r

    sheet_map: Dict[str, Dict[str, Any]] = {}
    for r in sheet_records:
        k = make_key(r)
        if k:
            sheet_map[k] = r

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

            # Price comparison
            bq_price = normalize_price(bq_r.get("spot_ltp"))
            sh_price = normalize_price(sh_r.get("spot_ltp") or sh_r.get("fut_ltp"))

            # Timestamp comparison
            bq_ts = parse_timestamp(bq_r.get("snapshot_timestamp"))
            sh_ts = parse_timestamp(sh_r.get("timestamp_ist") or sh_r.get("timestamp"))

            # Value check
            price_mismatch = False
            if bq_price is not None and sh_price is not None and bq_price > 0:
                pct_diff = abs(bq_price - sh_price) / bq_price * 100.0
                if pct_diff > price_tol_pct:
                    price_mismatch = True

            # Timestamp check
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


def load_records_from_csv(file_path: str) -> List[Dict[str, Any]]:
    """Load records from a CSV file with automatic header normalization."""
    records = []
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            normalized = {}
            for k, v in row.items():
                if not k:
                    continue
                clean_k = k.strip().lower().replace(" ", "_").replace("(", "").replace(")", "").replace("%", "pct")
                normalized[clean_k] = v
            # Alias common fields
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
    """Write reconciliation details to CSV."""
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
            # Fetch BigQuery
            bq_client = get_bigquery_client()
            query = f"SELECT * FROM `{bq_client.project}.{BQ_DATASET_ID}.option_predictions_live`"
            df = bq_client.query(query).to_dataframe()
            bq_records = df.to_dict(orient="records")
            print(f"[OK] Fetched {len(bq_records)} rows from BigQuery option_predictions_live.")

            # Fetch Sheet
            gc = get_gspread_client()
            sh = gc.open_by_key(SHEET_ID)
            ws = sh.worksheet("FORENSIC_LIVE")
            all_values = ws.get_all_values()
            if len(all_values) > 1:
                headers = [h.strip().lower().replace(" ", "_") for h in all_values[0]]
                for r in all_values[1:]:
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

    result = reconcile_records(bq_records, sheet_records)
    summary = result["summary"]

    print("\n" + "=" * 65)
    print("  BIGQUERY <-> OPTION_SHEET DETERMINISTIC RECONCILIATION REPORT")
    print("=" * 65)
    print(f"  Total Keys Evaluated:    {summary['total_keys_evaluated']}")
    print(f"  MATCH:                   {summary['match_count']} ({summary['match_pct']}%)")
    print(f"  BQ_ONLY:                 {summary['bq_only_count']}")
    print(f"  SHEET_ONLY:              {summary['sheet_only_count']}")
    print(f"  VALUE_MISMATCH:          {summary['value_mismatch_count']}")
    print(f"  TIMESTAMP_MISMATCH:      {summary['timestamp_mismatch_count']}")
    print("=" * 65)
    print(f"  Authoritative Producer:  {result['authoritativeness']['primary_producer']}")
    print(f"  Rule:                    {result['authoritativeness']['reconciliation_rule']}")
    print("=" * 65 + "\n")

    if args.output_csv:
        export_reconciliation_csv(result["details"], args.output_csv)
        print(f"[OK] Reconciliation CSV saved to: {args.output_csv}")

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"[OK] Reconciliation JSON saved to: {args.output_json}")


if __name__ == "__main__":
    main()

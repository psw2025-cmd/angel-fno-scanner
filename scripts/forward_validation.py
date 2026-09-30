#!/usr/bin/env python3
"""Read-only Target A/B forward-validation harness.
Writes evidence only under C:\\AngelFNO_Workstation\\reports.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = Path(r"C:\AngelFNO_Workstation\reports")
DATA = ROOT / "data"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

def now_ist():
    return dt.datetime.now(IST)

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def freeze_target_a():
    src = DATA / "next_day_gap_predictions.json"
    if not src.exists():
        raise SystemExit("Target A source missing: data/next_day_gap_predictions.json")
    stamp = now_ist()
    source_data = load_json(src)
    source_date = str(source_data.get("date", ""))
    if source_date != stamp.strftime("%Y-%m-%d"):
        out = REPORTS / f"TargetA_FREEZE_{stamp:%Y%m%d}.json"
        write_json(out, {"freeze_timestamp_ist": stamp.isoformat(), "status": "BLOCKED_STALE_SOURCE",
                         "source_date": source_date, "expected_date": stamp.strftime("%Y-%m-%d"),
                         "source_sha256": sha256(src)})
        raise SystemExit(f"Target A source is stale: {source_date}; expected {stamp:%Y-%m-%d}")
    out = REPORTS / f"TargetA_FREEZE_{stamp:%Y%m%d}.json"
    payload = {
        "freeze_timestamp_ist": stamp.isoformat(),
        "source": str(src),
        "source_sha256": sha256(src),
        "prediction": load_json(src),
        "status": "FROZEN_BEFORE_OPEN",
    }
    write_json(out, payload)
    print(f"[PASS] Target A frozen: {out}")
def snapshot_target_b():
    src = DATA / "latest_predictions.json"
    rows = load_json(src)
    stamp = now_ist()
    result = {"snapshot_timestamp_ist": stamp.isoformat(), "source_sha256": sha256(src),
              "status": "PAPER_ONLY", "CE": [], "PE": [], "volume_field_status": "MISSING_IF_NOT_PRESENT"}
    ce, pe = [], []
    for row in rows:
        for side, ltp_key, gain_key, oi_key, spread_key in (
            ("CE", "ce_ltp", "ce_chg_pct", "ce_oi", "ce_bid_ask_spread"),
            ("PE", "pe_ltp", "pe_chg_pct", "pe_oi", "pe_bid_ask_spread"),
        ):
            ltp = row.get(ltp_key)
            gain = row.get(gain_key)
            oi = row.get(oi_key)
            spread = row.get(spread_key)
            if ltp is None or gain is None or oi is None or oi <= 0:
                continue
            item = {
                "symbol": row.get("symbol"),
                "side": side,
                "ltp": ltp,
                "gain_pct": gain,
                "oi": oi,
                "volume": row.get(f"{side.lower()}_volume"),
                "bid_ask_spread": spread,
                "expiry": row.get("expiry"),
                "snapshot_timestamp": row.get("snapshot_timestamp"),
            }
            (ce if side == "CE" else pe).append(item)
    ce.sort(key=lambda x: x["gain_pct"], reverse=True)
    pe.sort(key=lambda x: x["gain_pct"], reverse=True)
    result["CE"] = {"top1": ce[:1], "top3": ce[:3], "top5": ce[:5]}
    result["PE"] = {"top1": pe[:1], "top3": pe[:3], "top5": pe[:5]}
    if any(x["volume"] is not None for x in ce + pe):
        result["volume_field_status"] = "AVAILABLE"
    out = REPORTS / f"TargetB_SNAPSHOT_{stamp:%Y%m%d_%H%M%S}.json"
    write_json(out, result)
    print(f"[PASS] Target B PAPER snapshot: {out}")

def reconcile_target_a(actual_path):
    actual = load_json(Path(actual_path))
    freezes = sorted(REPORTS.glob("TargetA_FREEZE_*.json"))
    if not freezes:
        raise SystemExit("No Target A freeze found.")
    frozen = load_json(freezes[-1])
    predictions = frozen["prediction"]
    by_symbol = {str(x.get("symbol")): x for x in actual}
    reconciled = []
    for item in predictions.get("top_ce_picks", []) + predictions.get("top_pe_picks", []):
        sym = str(item.get("symbol"))
        actual_open = by_symbol.get(sym, {}).get("open")
        expected = item.get("expected_gap_pct")
        reconciled.append({"symbol": sym, "side": item.get("side"),
                           "expected_gap_pct": expected, "actual_open": actual_open,
                           "status": "RECONCILED" if actual_open is not None else "MISSING_ACTUAL_OPEN"})
    stamp = now_ist()
    out = REPORTS / f"TargetA_RECONCILE_{stamp:%Y%m%d_%H%M%S}.json"
    write_json(out, {"reconcile_timestamp_ist": stamp.isoformat(), "source_freeze": str(freezes[-1]),
                     "actual_source": str(actual_path), "rows": reconciled, "paper_only": True})
    print(f"[PASS] Target A reconciliation: {out}")
def monitor(mode):
    stamp = now_ist()
    REPORTS.mkdir(parents=True, exist_ok=True)
    files = {
        "next_day_gap_predictions": DATA / "next_day_gap_predictions.json",
        "latest_predictions": DATA / "latest_predictions.json",
        "system_health": DATA / "system_health.json",
    }
    checks = {}
    for name, path in files.items():
        checks[name] = {"exists": path.exists(),
                        "mtime_ist": dt.datetime.fromtimestamp(path.stat().st_mtime, IST).isoformat() if path.exists() else None}
    payload = {"timestamp_ist": stamp.isoformat(), "mode": mode, "paper_only": True, "checks": checks}
    out = REPORTS / f"MONITOR_{mode.upper()}_{stamp:%Y%m%d_%H%M%S}.json"
    write_json(out, payload)
    print(f"[PASS] Read-only monitor report: {out}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-target-a", action="store_true")
    parser.add_argument("--snapshot-target-b", action="store_true")
    parser.add_argument("--reconcile-target-a")
    parser.add_argument("--monitor", choices=["premarket", "market", "postmarket"])
    args = parser.parse_args()
    if args.freeze_target_a: freeze_target_a()
    elif args.snapshot_target_b: snapshot_target_b()
    elif args.reconcile_target_a: reconcile_target_a(args.reconcile_target_a)
    elif args.monitor: monitor(args.monitor)
    else: parser.print_help()

if __name__ == "__main__":
    main()

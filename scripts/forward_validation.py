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

def resolve_reports_dir():
    env_dir = os.getenv("ANGEL_REPORTS_DIR")
    if env_dir:
        return Path(env_dir)
    if os.name != "nt":
        wsl_path = Path("/mnt/c/AngelFNO_Workstation/reports")
        if wsl_path.parent.exists():
            return wsl_path
    return Path(r"C:\AngelFNO_Workstation\reports")

REPORTS = resolve_reports_dir()
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

def parse_timestamp(value):
    if not value: return None
    try: parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError: return None
    return (parsed.replace(tzinfo=IST) if parsed.tzinfo is None else parsed).astimezone(IST)

def next_nse_session(date_value):
    d = date_value if isinstance(date_value, dt.date) else dt.date.fromisoformat(str(date_value)[:10])
    holidays = {"2026-01-26","2026-03-03","2026-03-26","2026-03-31","2026-04-03","2026-04-14","2026-05-01","2026-05-28","2026-06-26","2026-09-14","2026-10-02","2026-10-20","2026-11-10","2026-11-24","2026-12-25"}
    for _ in range(370):
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and d.isoformat() not in holidays: return d
    raise RuntimeError("Could not determine next NSE session")

def resolve_target_session(prediction):
    generated = parse_timestamp(prediction.get("prediction_generated_at") or prediction.get("timestamp_ist") or prediction.get("generated_at"))
    declared = str(prediction.get("target_market_session_date") or "").strip()[:10]
    if declared: return dt.date.fromisoformat(declared), generated, "DECLARED_TARGET_SESSION"
    if generated: return next_nse_session(generated.date()), generated, "DERIVED_NEXT_NSE_SESSION"
    return None, None, "MISSING_GENERATION_TIMESTAMP"

def validate_target_a_metadata(prediction, now=None):
    now = now or now_ist()
    target, generated, basis = resolve_target_session(prediction)
    if target is None or generated is None: return False, {"reason":"MISSING_GENERATION_TIMESTAMP","basis":basis}
    if target < now.date(): return False, {"reason":"TARGET_SESSION_ALREADY_PASSED","target_market_session_date":target.isoformat(),"basis":basis}
    if generated > now: return False, {"reason":"GENERATION_TIME_IN_FUTURE","basis":basis}
    if now - generated > dt.timedelta(days=5): return False, {"reason":"GENERATION_TOO_OLD","basis":basis}
    return True, {"target_market_session_date":target.isoformat(),"prediction_generated_at":generated.isoformat(),"basis":basis}

def freeze_target_a():
    src = DATA / "next_day_gap_predictions.json"
    if not src.exists():
        raise SystemExit("Target A source missing: data/next_day_gap_predictions.json")
    stamp = now_ist()
    source_data = load_json(src)
    ok, meta = validate_target_a_metadata(source_data, stamp)
    out = REPORTS / f"TargetA_FREEZE_{stamp:%Y%m%d}.json"
    if not ok or meta.get("target_market_session_date") != stamp.strftime("%Y-%m-%d"):
        write_json(out, {"freeze_timestamp_ist": stamp.isoformat(), "status": "BLOCKED_STALE_OR_MISMATCH",
                         "source_sha256": sha256(src), **meta})
        raise SystemExit(f"Target A not valid for today's session: {meta}")
    payload = {
        "freeze_timestamp_ist": stamp.isoformat(),
        "source": str(src),
        "source_sha256": sha256(src),
        "prediction": source_data,
        "status": "FROZEN_BEFORE_OPEN",
        **meta,
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
                "bid_ask_spread": spread if spread is not None else row.get(f"{side.lower()}_spread"),
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
    out = REPORTS / f"TargetB_SNAPSHOT_{stamp:%Y%m%d_%H%M%S_%f}.json"
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

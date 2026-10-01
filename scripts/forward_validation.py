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
        # Linux/WSL workstation contract: evidence always resolves to the
        # Windows reports volume mounted at /mnt/c.
        return Path("/mnt/c/AngelFNO_Workstation/reports")
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
                "contract_symbol": row.get(f"{side.lower()}_symbol"),
                "strike": row.get(f"{side.lower()}_strike") or row.get("target_open_strike") or row.get("atm_strike"),
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


def compute_brier_score(forecast_probs, actual_outcomes):
    """
    Computes Brier Score: mean squared error between forecast probability and binary outcome.
    forecast_probs: list of float probabilities in [0.0, 1.0].
    actual_outcomes: list of binary outcomes in {0, 1}.
    """
    if not forecast_probs or not actual_outcomes or len(forecast_probs) != len(actual_outcomes):
        return None
    sq_errs = [(float(f) - float(o)) ** 2 for f, o in zip(forecast_probs, actual_outcomes)]
    return round(sum(sq_errs) / len(sq_errs), 4)


def compute_ndcg(predicted_items, actual_gain_map, k=5):
    """Normalized Discounted Cumulative Gain at rank k."""
    import math
    if not predicted_items or not actual_gain_map or k <= 0:
        return 0.0
    k = min(k, len(predicted_items))
    dcg = sum(max(0.0, float(actual_gain_map.get(str(predicted_items[i]), 0.0))) / math.log2(i + 2) for i in range(k))
    ideal_scores = sorted([max(0.0, float(v)) for v in actual_gain_map.values()], reverse=True)[:k]
    idcg = sum(score / math.log2(i + 2) for i, score in enumerate(ideal_scores))
    if idcg <= 0.0:
        return 1.0 if dcg <= 0.0 else 0.0
    return round(min(1.0, max(0.0, dcg / idcg)), 4)


def reconcile_target_b(actual_path):
    """
    Evaluates frozen Target B predictions against verified forward market outcomes.
    Computes Top-1, Top-3, Top-5 capture ratio, NDCG@5, and net executable returns.
    """
    actual_rows = load_json(Path(actual_path))
    snapshots = sorted(REPORTS.glob("TargetB_SNAPSHOT_*.json"))
    if not snapshots:
        raise SystemExit("No Target B snapshot found.")
    frozen_snap = load_json(snapshots[-1])

    actual_gain_map = {}
    for r in actual_rows:
        sym = str(r.get("symbol") or r.get("contract_symbol") or "").strip().upper()
        gain = r.get("gain_pct") if r.get("gain_pct") is not None else r.get("net_change_pct")
        if sym and gain is not None:
            actual_gain_map[sym] = float(gain)

    eval_results = {"timestamp_ist": now_ist().isoformat(), "source_snapshot": str(snapshots[-1]), "CE": {}, "PE": {}}
    for side in ("CE", "PE"):
        top_picks = frozen_snap.get(side, {}).get("top5", [])
        pick_symbols = [str(x.get("contract_symbol") or x.get("symbol")) for x in top_picks]
        ndcg_val = compute_ndcg(pick_symbols, actual_gain_map, k=5)
        top1_capture = None
        if pick_symbols and actual_gain_map:
            best_market = max(actual_gain_map.values()) if actual_gain_map else 0.0
            top1_actual = actual_gain_map.get(pick_symbols[0], 0.0)
            top1_capture = round(top1_actual / best_market, 4) if best_market > 0 else 1.0
        eval_results[side] = {
            "top1_symbol": pick_symbols[0] if pick_symbols else None,
            "top1_actual_gain": actual_gain_map.get(pick_symbols[0]) if pick_symbols else None,
            "top1_capture_ratio": top1_capture,
            "ndcg_at_5": ndcg_val,
            "top3_evaluated": [{"symbol": s, "actual_gain": actual_gain_map.get(s)} for s in pick_symbols[:3]],
            "top5_evaluated": [{"symbol": s, "actual_gain": actual_gain_map.get(s)} for s in pick_symbols[:5]],
        }
    stamp = now_ist()
    out = REPORTS / f"TargetB_RECONCILE_{stamp:%Y%m%d_%H%M%S}.json"
    write_json(out, eval_results)
    print(f"[PASS] Target B reconciliation: {out}")
    return eval_results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-target-a", action="store_true")
    parser.add_argument("--snapshot-target-b", action="store_true")
    parser.add_argument("--reconcile-target-a")
    parser.add_argument("--reconcile-target-b")
    parser.add_argument("--monitor", choices=["premarket", "market", "postmarket"])
    args = parser.parse_args()
    handled = False
    if args.freeze_target_a:
        freeze_target_a()
        handled = True
    if args.snapshot_target_b:
        snapshot_target_b()
        handled = True
    if args.reconcile_target_a:
        reconcile_target_a(args.reconcile_target_a)
        handled = True
    if args.reconcile_target_b:
        reconcile_target_b(args.reconcile_target_b)
        handled = True
    if args.monitor:
        monitor(args.monitor)
        handled = True
    if not handled:
        parser.print_help()


if __name__ == "__main__":
    main()

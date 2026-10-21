"""Saved-history multi-bagger screen. Paper only. No broker orders.

The constants below are the definition. They were chosen from the length of
the saved archive, before the hit rate was computed. Do not edit them to
lift the score.

A hit is a raw spot at least 2.0 times the signal spot, 5 NSE sessions later.
market_calendar decides which dates are sessions. Prices come from git
versions of data/latest_predictions.json through scripts/forward_validation.load_json
for the working copy, and the same JSON shape for older commits.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import math
import os
import subprocess
import sys
from datetime import date, datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import market_calendar

_LOADER_PATH = ROOT / "scripts" / "forward_validation.py"
_loader_spec = importlib.util.spec_from_file_location("forward_validation_prices", _LOADER_PATH)
_loader = importlib.util.module_from_spec(_loader_spec)
_loader_spec.loader.exec_module(_loader)
load_json = _loader.load_json

# Frozen definition. See MULTIBAGGER_PAPER_20261021.md.
HORIZON_SESSIONS = 5
HIT_MULTIPLE = 2.0
TOP_N = 5
ENTRY_SLIPPAGE = 0.001
EXIT_SLIPPAGE = 0.001
ROUND_TRIP_FEE = 0.001
CAPITAL_INR = 100_000
INDEX_SYMBOLS = frozenset({
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "NIFTYNXT50",
    "NIFTYFPI",
})
HISTORY_FILE = "data/latest_predictions.json"
SIGNAL_CSV = ROOT / "data" / "multibagger_signals_20261021.csv"


def paper_status():
    paper = os.environ.get("PAPER_MODE")
    live = os.environ.get("LIVE_ORDER_AUTHORITY")
    return {
        "PAPER_MODE": paper,
        "LIVE_ORDER_AUTHORITY": live,
        "paper_safe": paper == "1" and live == "0",
        "orders_placed": False,
    }


def require_paper():
    status = paper_status()
    if not status["paper_safe"]:
        raise RuntimeError(
            "Refusing to write. PAPER_MODE must be 1 and LIVE_ORDER_AUTHORITY must be 0. "
            f"Read PAPER_MODE={status['PAPER_MODE']!r} LIVE_ORDER_AUTHORITY={status['LIVE_ORDER_AUTHORITY']!r}."
        )
    return status


def as_float(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def paper_would_write(entry_price):
    """Local dry-run gate. A simulated row exists only for a positive entry price.

    This does not call Google Sheets, BigQuery, or a broker.
    """
    price = as_float(entry_price)
    return price is not None and price > 0


def snapshot_ist(value):
    text = str(value).strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=market_calendar.IST)
    return parsed.astimezone(market_calendar.IST)


def session_is_trading_day(day: date) -> bool:
    probe = datetime.combine(day, time(12, 0), tzinfo=market_calendar.IST)
    try:
        return bool(market_calendar.is_trading_day(probe))
    except RuntimeError:
        return False


def _rows_to_cross_section(rows):
    spots = {}
    ce_chg = {}
    oi_chg = {}
    latest = None
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        spot = as_float(row.get("spot_ltp"))
        if not symbol or spot is None or spot <= 0:
            continue
        try:
            stamp = snapshot_ist(row.get("snapshot_timestamp"))
        except (TypeError, ValueError):
            continue
        if latest is None or stamp > latest:
            latest = stamp
        spots[symbol] = spot
        ce_chg[symbol] = as_float(row.get("ce_chg_pct"))
        oi_chg[symbol] = as_float(row.get("ce_oi_change_pct"))
    if latest is None:
        return None
    return {
        "snapshot_ist": latest,
        "spots": spots,
        "ce_chg": ce_chg,
        "oi_chg": oi_chg,
    }


def keep_latest_sessions(cross_sections):
    """One cross-section per trading day: the latest snapshot that day."""
    chosen = {}
    dropped_non_sessions = 0
    for section in cross_sections:
        if not section:
            continue
        day = section["snapshot_ist"].date()
        if not session_is_trading_day(day):
            dropped_non_sessions += 1
            continue
        current = chosen.get(day)
        if current is None or section["snapshot_ist"] > current["snapshot_ist"]:
            chosen[day] = {
                "session_date": day.isoformat(),
                "snapshot_ist": section["snapshot_ist"].isoformat(),
                "spots": section["spots"],
                "ce_chg": section["ce_chg"],
                "oi_chg": section["oi_chg"],
            }
    sessions = [chosen[day] for day in sorted(chosen)]
    return sessions, dropped_non_sessions


def _git_snapshot_texts():
    log = subprocess.check_output(
        ["git", "log", "--follow", "--pretty=format:%H", "--", HISTORY_FILE],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    texts = []
    for sha in log.split():
        raw = subprocess.check_output(
            ["git", "show", f"{sha}:{HISTORY_FILE}"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        texts.append(raw)
    return texts


def load_saved_sessions():
    """Load spot cross-sections from saved prediction snapshots.

    The working copy uses the existing JSON loader. Older days come from git
    versions of the same file. No new price service is called.
    """
    sections = []
    working = ROOT / HISTORY_FILE
    if working.is_file():
        sections.append(_rows_to_cross_section(load_json(working)))
    for raw in _git_snapshot_texts():
        sections.append(_rows_to_cross_section(json.loads(raw)))
    return keep_latest_sessions(sections)


def net_return(entry_spot, exit_spot):
    entry_fill = entry_spot * (1.0 + ENTRY_SLIPPAGE)
    exit_fill = exit_spot * (1.0 - EXIT_SLIPPAGE)
    return (exit_fill / entry_fill) - 1.0 - ROUND_TRIP_FEE


def score_sessions(sessions):
    """Score the frozen rule. Features stop at the signal snapshot."""
    sessions = list(sessions or [])
    signals = []
    baseline_hits = 0
    baseline_misses = 0
    baseline_missing = 0
    skipped_no_index = []
    last_signal_index = len(sessions) - 1 - HORIZON_SESSIONS
    for index in range(1, last_signal_index + 1):
        current = sessions[index]
        prior = sessions[index - 1]
        later = sessions[index + HORIZON_SESSIONS]
        nifty_now = current["spots"].get("NIFTY")
        nifty_prior = prior["spots"].get("NIFTY")
        if not nifty_now or not nifty_prior:
            skipped_no_index.append(current["session_date"])
            continue
        nifty_momentum = nifty_now / nifty_prior - 1.0
        eligible = []
        universe = set(current["spots"]) | set(later["spots"])
        for symbol in sorted(universe):
            if symbol in INDEX_SYMBOLS:
                continue
            entry = current["spots"].get(symbol)
            exit_spot = later["spots"].get(symbol)
            if entry is None or entry <= 0:
                continue
            if exit_spot is None or exit_spot <= 0:
                baseline_missing += 1
                continue
            if exit_spot / entry >= HIT_MULTIPLE:
                baseline_hits += 1
            else:
                baseline_misses += 1
        for symbol, entry in current["spots"].items():
            if symbol in INDEX_SYMBOLS or entry <= 0:
                continue
            prior_spot = prior["spots"].get(symbol)
            ce_change = current["ce_chg"].get(symbol)
            if prior_spot is None or prior_spot <= 0 or ce_change is None:
                continue
            momentum = entry / prior_spot - 1.0
            relative = momentum - nifty_momentum
            if momentum <= 0 or relative <= 0 or ce_change <= 0:
                continue
            eligible.append((relative, symbol, momentum, ce_change, entry))
        eligible.sort(key=lambda item: (-item[0], item[1]))
        for rank, (relative, symbol, momentum, ce_change, entry) in enumerate(eligible[:TOP_N], start=1):
            exit_spot = later["spots"].get(symbol)
            oi_change = current["oi_chg"].get(symbol)
            if exit_spot is None or exit_spot <= 0:
                outcome = "MISSING"
                return_pct = None
                hit = "MISSING"
                exit_value = None
            else:
                multiple = exit_spot / entry
                return_pct = (multiple - 1.0) * 100.0
                outcome = f"{return_pct:.4f} percent"
                hit = "HIT" if multiple >= HIT_MULTIPLE else "MISS"
                exit_value = exit_spot
            oi_text = "blank" if oi_change is None else f"{oi_change:.4f}"
            features = (
                f"momentum_1s={momentum:.6f}; "
                f"relative_strength_vs_nifty={relative:.6f}; "
                f"ce_chg_pct={ce_change:.4f}; "
                f"ce_oi_change_pct={oi_text} (recorded, not a gate); "
                "volume=skipped; delivery=skipped; earnings=skipped"
            )
            signals.append({
                "symbol": symbol,
                "signal_time": current["snapshot_ist"],
                "signal_session": current["session_date"],
                "outcome_session": later["session_date"],
                "features_used": features,
                "momentum_1s": momentum,
                "relative_strength": relative,
                "ce_chg_pct": ce_change,
                "ce_oi_change_pct": oi_change,
                "entry_spot": entry,
                "exit_spot": exit_value,
                "later_outcome": outcome,
                "return_pct": return_pct,
                "hit_or_miss": hit,
                "rank": rank,
                "paper_row": "WRITE_SIMULATED" if paper_would_write(entry) else "SKIP_NO_ENTRY_PRICE",
                "horizon_sessions": HORIZON_SESSIONS,
                "hit_multiple": HIT_MULTIPLE,
            })
    hits = sum(1 for row in signals if row["hit_or_miss"] == "HIT")
    misses = sum(1 for row in signals if row["hit_or_miss"] == "MISS")
    missing = sum(1 for row in signals if row["hit_or_miss"] == "MISSING")
    scored = hits + misses
    accuracy = (hits / scored) if scored else None
    baseline_scored = baseline_hits + baseline_misses
    baseline = (baseline_hits / baseline_scored) if baseline_scored else None
    pnl_rows = [row for row in signals if row["exit_spot"] is not None and row["entry_spot"] > 0]
    if pnl_rows:
        allocation = CAPITAL_INR / len(pnl_rows)
        pnl = 0.0
        for row in pnl_rows:
            pnl += allocation * net_return(row["entry_spot"], row["exit_spot"])
    else:
        allocation = None
        pnl = None
    return {
        "definition": {
            "horizon_sessions": HORIZON_SESSIONS,
            "hit_multiple": HIT_MULTIPLE,
            "top_n": TOP_N,
            "entry_slippage": ENTRY_SLIPPAGE,
            "exit_slippage": EXIT_SLIPPAGE,
            "round_trip_fee": ROUND_TRIP_FEE,
            "capital_inr": CAPITAL_INR,
        },
        "session_dates": [row["session_date"] for row in sessions],
        "session_count": len(sessions),
        "skipped_no_index": skipped_no_index,
        "signals": signals,
        "n_signals": len(signals),
        "hits": hits,
        "misses": misses,
        "missing_outcomes": missing,
        "scored": scored,
        "accuracy": accuracy,
        "baseline_hits": baseline_hits,
        "baseline_misses": baseline_misses,
        "baseline_missing": baseline_missing,
        "baseline_scored": baseline_scored,
        "baseline_accuracy": baseline,
        "simulated_pnl_per_1_lakh_inr": pnl,
        "allocation_per_scored_name_inr": allocation,
        "paper_rows_written": sum(1 for row in signals if row["paper_row"] == "WRITE_SIMULATED"),
        "paper_rows_skipped": sum(1 for row in signals if row["paper_row"] != "WRITE_SIMULATED"),
    }


def _paper_controls():
    return {
        "missing_entry_writes": paper_would_write(None),
        "blank_entry_writes": paper_would_write(""),
        "zero_entry_writes": paper_would_write(0),
        "negative_entry_writes": paper_would_write(-5),
        "positive_entry_writes": paper_would_write(100.0),
    }


def write_signal_csv(path: Path, signals):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "symbol",
        "signal_time",
        "signal_session",
        "outcome_session",
        "features_used",
        "later_outcome",
        "hit_or_miss",
        "entry_spot",
        "exit_spot",
        "return_pct",
        "rank",
        "paper_row",
        "horizon_sessions",
        "hit_multiple",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in signals:
            writer.writerow(row)


def main():
    status = require_paper()
    clock = market_calendar.market_session_state()
    sessions, dropped = load_saved_sessions()
    scored = score_sessions(sessions)
    controls = _paper_controls()
    write_signal_csv(SIGNAL_CSV, scored["signals"])
    payload = {
        "paper": status,
        "orders_placed": False,
        "clock": clock,
        "non_session_snapshots_dropped": dropped,
        "paper_controls": controls,
        "csv": str(SIGNAL_CSV),
        **{key: value for key, value in scored.items() if key != "signals"},
        "signal_preview": scored["signals"],
    }
    print(json.dumps(payload, indent=2, default=str))
    controls_ok = (
        controls["missing_entry_writes"] is False
        and controls["blank_entry_writes"] is False
        and controls["zero_entry_writes"] is False
        and controls["negative_entry_writes"] is False
        and controls["positive_entry_writes"] is True
    )
    if not controls_ok:
        return 1
    if scored["accuracy"] is None:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

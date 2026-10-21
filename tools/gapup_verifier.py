"""Copy an already written gap forecast into a local log, then fill a result later.

market_bot remains the only production prediction writer. This file does not
place orders, does not call a broker, and does not write BigQuery or Google
Sheets. A missing outcome stays missing. A hit rate is not calculated here.
"""
import json
import os
import sys
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import market_calendar

IST = ZoneInfo("Asia/Kolkata")
DEFAULT_SOURCE = REPO / "data" / "next_day_gap_predictions.json"
DEFAULT_LOG = Path(r"C:\AngelFNO_Workstation\angel-agent-supervisor\logs\gapup_forward_log.jsonl")


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


def _parse_ist(value):
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = dt.datetime.strptime(text[:19], fmt)
                break
            except ValueError:
                parsed = None
        if parsed is None:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)
    return parsed.astimezone(IST)


def target_session_date(forecast_dt):
    """The session whose opening gap this forecast can still be early for."""
    state = market_calendar.market_session_state(forecast_dt)
    if state.get("status") == "BEFORE_OPEN":
        return forecast_dt.date()
    probe = dt.datetime.combine(forecast_dt.date(), dt.time(10, 0), tzinfo=IST) + dt.timedelta(days=1)
    for _ in range(21):
        if market_calendar.market_session_state(probe).get("status") == "OPEN":
            return probe.date()
        probe += dt.timedelta(days=1)
    return None


def session_still_ahead(target_date, now):
    """True only when the gap for target_date has not started."""
    if target_date is None or now is None:
        return False
    if now.date() < target_date:
        return True
    if now.date() > target_date:
        return False
    state = market_calendar.market_session_state(now)
    return state.get("status") == "BEFORE_OPEN"


def load_log(path):
    path = Path(path)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _append(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def verify(predictions=None, outcomes=None):
    del outcomes
    paired = 0
    for row in predictions or []:
        if not isinstance(row, dict):
            continue
        predicted = row.get("predicted_at")
        outcome_at = row.get("outcome_at")
        if predicted and row.get("actual_gap_pct") is not None and outcome_at:
            if str(predicted) < str(outcome_at):
                paired += 1
    return {
        "status": "NOT_MEASURED",
        "sample_size": paired,
        "hits": None,
        "accuracy": None,
        "note": "No hit rate is calculated. A blank outcome stays blank. This is not profit.",
        "orders_placed": False,
    }


def record_from_source(source_path=None, log_path=None, now=None):
    """Copy top call and top put only when the forecast is still before its session."""
    safety = require_paper()
    source_path = Path(source_path or DEFAULT_SOURCE)
    log_path = Path(log_path or os.environ.get("GAPUP_FORWARD_LOG") or DEFAULT_LOG)
    now = now or dt.datetime.now(IST)
    result = {
        **safety,
        "source": str(source_path),
        "log": str(log_path),
        "recorded": 0,
        "skipped": [],
        "outcomes_filled": 0,
    }
    if not source_path.is_file():
        result["status"] = "MISSING"
        result["note"] = "Prediction file is absent. No symbol was guessed."
        return result
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    stamped = _parse_ist(payload.get("timestamp_ist") or payload.get("prediction_generated_at"))
    calls = payload.get("top_ce_picks") or []
    puts = payload.get("top_pe_picks") or []
    if not calls and not puts:
        result["status"] = "MISSING"
        result["note"] = "The file has no call list and no put list. Top call and top put stay missing."
        return result
    if stamped is None:
        result["status"] = "MISSING"
        result["note"] = "The file has no prediction time. Nothing was copied."
        return result
    target = target_session_date(stamped)
    if not session_still_ahead(target, now):
        result["status"] = "NOT_RECORDED"
        result["target_session_date"] = target.isoformat() if target else None
        result["note"] = (
            "The saved forecast is for a session that has already started or passed. "
            "It was not copied, and no outcome was invented."
        )
        return result
    existing = load_log(log_path)
    seen = {(row.get("predicted_at"), row.get("symbol"), row.get("side")) for row in existing}
    picked = []
    for side, rows in (("CE", calls), ("PE", puts)):
        if not rows:
            result["skipped"].append({"side": side, "reason": "MISSING"})
            continue
        first = rows[0]
        symbol = str(first.get("symbol") or "").strip()
        score = first.get("score")
        if not symbol or score is None:
            result["skipped"].append({"side": side, "reason": "MISSING"})
            continue
        predicted_at = stamped.isoformat()
        key = (predicted_at, symbol, side)
        if key in seen:
            result["skipped"].append({"side": side, "symbol": symbol, "reason": "ALREADY_RECORDED"})
            continue
        row = {
            "predicted_at": predicted_at,
            "target_session_date": target.isoformat(),
            "symbol": symbol,
            "side": side,
            "score": score,
            "expected_gap_pct": first.get("expected_gap_pct"),
            "source": str(source_path),
            "writer": "gapup_verifier_copy",
            "production_writer": "market_bot",
            "actual_gap_pct": None,
            "outcome_at": None,
            "hit": None,
        }
        _append(log_path, row)
        picked.append({"symbol": symbol, "side": side, "score": score})
        result["recorded"] += 1
    result["status"] = "RECORDED" if result["recorded"] else "NOT_RECORDED"
    result["picks"] = picked
    result["note"] = "Outcomes were left blank. This copy is not a new production prediction."
    return result


def fill_outcome(prediction_key, actual_gap_pct, outcome_at, log_path=None):
    """Fill one blank outcome. The caller must supply the number and a later time."""
    safety = require_paper()
    log_path = Path(log_path or os.environ.get("GAPUP_FORWARD_LOG") or DEFAULT_LOG)
    when = _parse_ist(outcome_at)
    if when is None or actual_gap_pct is None:
        raise RuntimeError("An outcome time and an actual gap are required. Nothing was guessed.")
    try:
        actual = float(actual_gap_pct)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("The actual gap must be a number supplied by the caller.") from exc
    rows = load_log(log_path)
    updated = 0
    for row in rows:
        key = (row.get("predicted_at"), row.get("symbol"), row.get("side"))
        if key != tuple(prediction_key):
            continue
        predicted = _parse_ist(row.get("predicted_at"))
        if predicted is None or when <= predicted:
            raise RuntimeError("The outcome time is not after the prediction time. The row was left blank.")
        if row.get("actual_gap_pct") is not None:
            raise RuntimeError("This row already has an outcome. It was not overwritten.")
        row["actual_gap_pct"] = actual
        row["outcome_at"] = when.isoformat()
        row["hit"] = None
        updated += 1
    if updated != 1:
        raise RuntimeError("No matching blank prediction was found. No row was invented.")
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    log_path.write_text(text, encoding="utf-8")
    return {
        **safety,
        "status": "OUTCOME_STORED",
        "updated": updated,
        "hit": None,
        "accuracy": None,
        "note": "The gap number was stored. Hit rate is not available.",
    }


def _price(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number <= 0:
        return None
    return number


def _bq_query(sql):
    import shutil
    import subprocess
    bq = shutil.which("bq") or shutil.which("bq.cmd")
    if not bq:
        return {"ok": False, "rows": [], "error": "bq command was not found"}
    try:
        result = subprocess.run(
            [bq, "query", "--project_id=fno-angel-prod-1790444589", "--use_legacy_sql=false",
             "--format=json", "--quiet", "--max_rows=1000", sql],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=180, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "rows": [], "error": type(exc).__name__}
    text = (result.stdout or "").strip()
    start = text.find("[")
    rows = None
    if start >= 0:
        try:
            rows = json.loads(text[start:])
        except ValueError:
            rows = None
    if result.returncode != 0 or not isinstance(rows, list):
        detail = ((result.stderr or "") + "\n" + text)[-500:]
        return {"ok": False, "rows": [], "error": detail or "bq query failed"}
    return {"ok": True, "rows": rows, "error": ""}


def _load_local_prices():
    prices = []
    latest = REPO / "data" / "latest_predictions.json"
    if latest.is_file():
        payload = json.loads(latest.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            when = _parse_ist(row.get("snapshot_timestamp") or row.get("source_timestamp"))
            symbol = str(row.get("symbol") or "").strip().upper()
            spot = _price(row.get("spot_ltp"))
            if when is None or not symbol or spot is None:
                continue
            prices.append({
                "symbol": symbol,
                "instrument": "SPOT",
                "price": spot,
                "at": when,
                "expected_gap_pct": row.get("expected_gap_pct"),
                "side": "",
                "kind": "snapshot",
                "source": str(latest),
            })
    if DEFAULT_SOURCE.is_file():
        payload = json.loads(DEFAULT_SOURCE.read_text(encoding="utf-8"))
        stamped = _parse_ist(payload.get("timestamp_ist") or payload.get("prediction_generated_at"))
        picks = list(payload.get("top_ce_picks") or []) + list(payload.get("top_pe_picks") or [])
        for pick in picks:
            if not isinstance(pick, dict):
                continue
            when = _parse_ist(pick.get("forecast_timestamp")) or stamped
            contract = str(pick.get("contract_symbol") or pick.get("forecast_contract") or "").strip().upper()
            entry = _price(pick.get("entry_ltp"))
            symbol = str(pick.get("symbol") or "").strip().upper()
            if when is None or not symbol or not contract or entry is None:
                continue
            prices.append({
                "symbol": symbol,
                "instrument": contract,
                "price": entry,
                "at": when,
                "expected_gap_pct": pick.get("expected_gap_pct"),
                "side": str(pick.get("side") or "").upper(),
                "kind": "signal",
                "source": str(DEFAULT_SOURCE),
            })
    return prices


def _score_later(earlier, later):
    """Score only two real prices. A missing direction is not counted as a hit or a miss."""
    entry = _price(earlier.get("price"))
    exit_price = _price(later.get("price"))
    if entry is None or exit_price is None:
        return None
    actual = (exit_price - entry) / entry * 100.0
    if earlier.get("instrument") != "SPOT":
        hit = actual >= 20.0
    else:
        try:
            expected = float(earlier.get("expected_gap_pct"))
        except (TypeError, ValueError):
            return None
        if expected == 0:
            return None
        hit = (actual > 0 and expected > 0) or (actual < 0 and expected < 0)
    return {"actual_pct": round(actual, 4), "hit": bool(hit), "exit_price": exit_price}


def _join_later_prices(prices):
    grouped = {}
    for item in prices:
        grouped.setdefault((item["symbol"], item["instrument"]), []).append(item)
    paired = []
    missing = 0
    subjects = [item for item in prices if item.get("kind") == "signal"] or [
        item for item in prices if item.get("kind") == "snapshot"
    ]
    seen = set()
    for item in subjects:
        key = (item["symbol"], item["instrument"], item["at"].isoformat())
        if key in seen:
            continue
        seen.add(key)
        later = []
        for other in grouped.get((item["symbol"], item["instrument"]), []):
            if other["at"] <= item["at"]:
                continue
            if market_calendar.market_session_state(other["at"]).get("status") != "OPEN":
                continue
            if _price(other.get("price")) is None:
                continue
            later.append(other)
        if not later:
            missing += 1
            continue
        nxt = min(later, key=lambda row: row["at"])
        scored = _score_later(item, nxt)
        if scored is None:
            missing += 1
            continue
        paired.append({"earlier": item, "later": nxt, "score": scored})
    return paired, missing, len(seen)


def measure_stored_outcomes():
    """Join a later open-session price when one exists. Do not invent the rest."""
    os.environ["PAPER_MODE"] = "1"
    os.environ["LIVE_ORDER_AUTHORITY"] = "0"
    safety = require_paper()
    prices = _load_local_prices()
    paired, missing_local, seen_local = _join_later_prices(prices)
    hits = sum(1 for item in paired if item["score"]["hit"])
    date_query = _bq_query(
        "SELECT FORMAT_DATE('%F', DATE(snapshot_timestamp)) AS cycle_date, "
        "COUNT(*) AS row_count FROM "
        "`fno-angel-prod-1790444589.fno_predictions.option_predictions_live` "
        "GROUP BY cycle_date ORDER BY cycle_date"
    )
    gap_query = _bq_query(
        "SELECT IFNULL(outcome, 'BLANK') AS outcome, COUNT(*) AS row_count FROM "
        "`fno-angel-prod-1790444589.fno_predictions.next_day_gap_predictions` "
        "GROUP BY outcome ORDER BY outcome"
    )
    bq_rows = date_query["rows"] if date_query["ok"] else []
    bq_count = 0
    for row in bq_rows:
        try:
            bq_count += int(row.get("row_count") or 0)
        except (TypeError, ValueError):
            continue
    open_later_dates = []
    for row in bq_rows:
        day = str(row.get("cycle_date") or "")
        try:
            probe = dt.datetime.fromisoformat(day + "T10:00:00").replace(tzinfo=IST)
        except ValueError:
            continue
        if market_calendar.market_session_state(probe).get("status") == "OPEN":
            open_later_dates.append(day)
    live_hits = 0
    live_denominator = 0
    live_missing = bq_count if date_query["ok"] else None
    spot_query = {"ok": True, "rows": [], "error": ""}
    if date_query["ok"] and len(bq_rows) >= 2:
        spot_query = _bq_query(
            "SELECT symbol, "
            "FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', snapshot_timestamp, 'Asia/Kolkata') AS at_ist, "
            "spot_ltp, expected_gap_pct FROM "
            "`fno-angel-prod-1790444589.fno_predictions.option_predictions_live`"
        )
        if not spot_query["ok"]:
            live_missing = None
        else:
            bq_prices = []
            for row in spot_query["rows"]:
                when = _parse_ist(row.get("at_ist"))
                spot = _price(row.get("spot_ltp"))
                symbol = str(row.get("symbol") or "").strip().upper()
                if when is None or spot is None or not symbol:
                    continue
                bq_prices.append({
                    "symbol": symbol,
                    "instrument": "SPOT",
                    "price": spot,
                    "at": when,
                    "expected_gap_pct": row.get("expected_gap_pct"),
                    "side": "",
                    "kind": "snapshot",
                    "source": "bigquery.option_predictions_live",
                })
            bq_paired, bq_missing, _bq_seen = _join_later_prices(bq_prices)
            live_hits = sum(1 for item in bq_paired if item["score"]["hit"])
            live_denominator = len(bq_paired)
            live_missing = bq_missing
            for item in bq_paired:
                if item not in paired:
                    paired.append(item)
    stored = 0
    if paired:
        log_path = Path(os.environ.get("GAPUP_FORWARD_LOG") or DEFAULT_LOG)
        existing = load_log(log_path)
        known = {(row.get("predicted_at"), row.get("symbol"), row.get("side"), row.get("instrument")) for row in existing}
        for item in paired:
            earlier = item["earlier"]
            later = item["later"]
            identity = (earlier["at"].isoformat(), earlier["symbol"], earlier.get("side") or "", earlier["instrument"])
            if identity in known:
                continue
            _append(log_path, {
                "predicted_at": earlier["at"].isoformat(),
                "outcome_at": later["at"].isoformat(),
                "symbol": earlier["symbol"],
                "side": earlier.get("side") or "",
                "instrument": earlier["instrument"],
                "entry_price": earlier["price"],
                "later_price": item["score"]["exit_price"],
                "actual_gap_pct": item["score"]["actual_pct"],
                "hit": item["score"]["hit"],
                "writer": "gapup_verifier_join",
                "production_writer": "market_bot",
                "fill": "simulated",
            })
            stored += 1
    hits = sum(1 for item in paired if item["score"]["hit"])
    report = {
        **safety,
        "orders_placed": False,
        "local_predictions_seen": seen_local,
        "denominator": len(paired),
        "hits": hits,
        "missing": missing_local,
        "outcomes_stored": stored,
        "hit_rate": None if not paired else round(hits / len(paired), 4),
        "bigquery_prediction_dates": bq_rows,
        "bigquery_prediction_rows": bq_count,
        "live_snapshot_denominator": live_denominator,
        "live_snapshot_hits": live_hits,
        "live_snapshot_missing": live_missing,
        "bigquery_open_session_dates": open_later_dates,
        "bigquery_gap_outcomes": gap_query["rows"] if gap_query["ok"] else [],
        "bigquery_errors": [item["error"] for item in (date_query, gap_query, spot_query) if not item["ok"]],
        "note": (
            "An outcome is stored only when a later open-session price for the same instrument exists. "
            "A blank later price stays missing. This is not profit."
        ),
    }
    if not paired:
        report["hit_rate"] = None
        report["hits"] = 0
    return report


def self_check():
    import tempfile

    os.environ["PAPER_MODE"] = "1"
    os.environ["LIVE_ORDER_AUTHORITY"] = "0"
    now = dt.datetime(2026, 10, 21, 2, 0, tzinfo=IST)
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        source = folder / "forecast.json"
        log_path = folder / "forward.jsonl"
        source.write_text(json.dumps({
            "timestamp_ist": "2026-10-21 01:00:00",
            "top_ce_picks": [{"symbol": "EXAMPLE", "side": "CE", "score": 1.0, "expected_gap_pct": 1.0}],
            "top_pe_picks": [{"symbol": "SAMPLE", "side": "PE", "score": 2.0, "expected_gap_pct": -1.0}],
        }), encoding="utf-8")
        recorded = record_from_source(source, log_path, now=now)
        if recorded["recorded"] != 2:
            raise SystemExit("self-check failed: fresh forecast was not copied")
        rows = load_log(log_path)
        if any(row.get("actual_gap_pct") is not None for row in rows):
            raise SystemExit("self-check failed: an outcome was filled early")
        stale = folder / "stale.json"
        stale.write_text(json.dumps({
            "timestamp_ist": "2026-10-09 22:45:05",
            "top_ce_picks": [{"symbol": "OLD", "side": "CE", "score": 9.0}],
            "top_pe_picks": [{"symbol": "OLD", "side": "PE", "score": 8.0}],
        }), encoding="utf-8")
        refused = record_from_source(stale, log_path, now=now)
        if refused["recorded"] != 0 or refused["status"] == "RECORDED":
            raise SystemExit("self-check failed: a passed session was copied")
        if any(row.get("symbol") == "OLD" for row in load_log(log_path)):
            raise SystemExit("self-check failed: an old symbol was written")
        key = (rows[0]["predicted_at"], rows[0]["symbol"], rows[0]["side"])
        try:
            fill_outcome(key, 3.0, "2026-10-21 00:30:00", log_path)
        except RuntimeError:
            pass
        else:
            raise SystemExit("self-check failed: an earlier outcome was accepted")
        filled = fill_outcome(key, 3.0, "2026-10-21 09:20:00", log_path)
        if filled.get("hit") is not None or filled.get("accuracy") is not None:
            raise SystemExit("self-check failed: a hit rate was invented")
        os.environ["LIVE_ORDER_AUTHORITY"] = "1"
        try:
            record_from_source(source, log_path, now=now)
        except RuntimeError:
            pass
        else:
            raise SystemExit("self-check failed: live authority was accepted")
        os.environ["LIVE_ORDER_AUTHORITY"] = "0"
    report = verify()
    report["self_check"] = "completed"
    report["paper"] = paper_status()
    return report


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--self-check"]:
        print(json.dumps(self_check(), indent=2))
        return 0
    safety = paper_status()
    if not safety["paper_safe"]:
        print(json.dumps({**safety, "status": "REFUSED", "note": "PAPER_MODE must be 1 and LIVE_ORDER_AUTHORITY must be 0."}, indent=2))
        return 2
    if argv[:1] == ["record"]:
        print(json.dumps(record_from_source(), indent=2))
        return 0
    if argv[:1] == ["measure"]:
        print(json.dumps(measure_stored_outcomes(), indent=2, default=str))
        return 0
    rows = load_log(Path(os.environ.get("GAPUP_FORWARD_LOG") or DEFAULT_LOG))
    report = verify(rows)
    report.update(safety)
    report["stored_predictions"] = len(rows)
    report["blank_outcomes"] = sum(1 for row in rows if row.get("actual_gap_pct") is None)
    print(json.dumps(report, indent=2))
    return 0 if rows else 2


if __name__ == "__main__":
    sys.exit(main())

"""Independent, PAPER-only reconciliation of dated external option-gainer snapshots.

Consumes supplied normalized records, not scraped HTML. No network, broker, order or
production-writer dependency. External observations must never modify advance picks.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
SOURCE = "moneycontrol_observation"
MIN_PREMIUM = 2.0


def _timestamp(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Missing timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamp needs timezone")
    return dt.astimezone(IST)


def _key(row):
    symbol = str(row.get("symbol", "")).strip().upper()
    side = str(row.get("side") or row.get("option_type") or "").strip().upper()
    if not symbol or side not in ("CE", "PE"):
        raise ValueError("Invalid symbol/side")
    expiry = str(row.get("expiry", "")).strip()
    try:
        expiry = datetime.strptime(expiry, "%Y-%m-%d").date().isoformat()
        strike = float(row["strike"])
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("Invalid expiry/strike; require ISO expiry and numeric strike") from exc
    if not 0 < strike < float("inf"):
        raise ValueError("Invalid strike")
    return symbol, expiry, strike, side


def reconcile(advance_picks, actual_rows, *, snapshot_at, source_url, as_of):
    """Return immutable-style evidence summary for one external snapshot.

    Prediction issue timestamps must precede snapshot and be from the same IST
    trading date. Contracts are matched on symbol, ISO expiry, strike and side.
    Malformed, duplicate, undated or future observations fail the whole snapshot.
    """
    snapshot = _timestamp(snapshot_at)
    now = _timestamp(as_of)
    if snapshot > now:
        raise ValueError("Future snapshot")
    if not str(source_url).startswith("https://www.moneycontrol.com/"):
        raise ValueError("Source URL must be identified")
    predictions = {}
    for pick in advance_picks:
        key = _key(pick)
        issued = _timestamp(pick.get("issued_at"))
        if issued >= snapshot or issued.date() != snapshot.date():
            raise ValueError("Prediction not demonstrably advance/same-day")
        if key in predictions:
            raise ValueError("Duplicate advance contract")
        predictions[key] = pick
    actuals = {}
    for row in actual_rows:
        key = _key(row)
        if key in actuals:
            raise ValueError("Duplicate observed contract")
        premium = float(row["ltp"])
        if not 0 <= premium < float("inf"):
            raise ValueError("Invalid observed premium")
        actuals[key] = premium
    matches = sorted(set(predictions) & set(actuals))
    tradable_matches = [key for key in matches if actuals[key] >= MIN_PREMIUM]
    return {
        "mode": "PAPER_ONLY", "order_authority": 0, "source": SOURCE,
        "source_url": source_url, "snapshot_at": snapshot.isoformat(),
        "as_of": now.isoformat(), "match_basis": "symbol+expiry+strike+side",
        "advance_contracts": len(predictions), "observed_contracts": len(actuals),
        "exact_matches": len(matches), "premium_eligible_matches": len(tradable_matches),
        "observed_below_min_premium": sum(v < MIN_PREMIUM for v in actuals.values()),
        "matched_contracts": [
            {"symbol": k[0], "expiry": k[1], "strike": k[2], "side": k[3],
             "observed_ltp": actuals[k], "premium_eligible": actuals[k] >= MIN_PREMIUM}
            for k in matches
        ],
        "qualification": "Premium threshold is not evidence of liquidity, executable price or profit",
    }

"""Market-session and pre-publication guards, independent of broker credentials."""
import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from tools.market_session_preflight import evaluate, require_allowed
from tools.check_freshness import validate

IST = ZoneInfo("Asia/Kolkata")


def when(y, mo, d, hour, minute=0):
    return dt.datetime(y, mo, d, hour, minute, tzinfo=IST)


@pytest.mark.parametrize("requested", ["OPEN", "EOD", "CLOSED"])
def test_diwwali_balipratipada_2026_never_publishes(requested):
    result = evaluate(requested, at=when(2026, 11, 10, 10))
    assert not result["can_scan"]
    assert result["market_status"] == "HOLIDAY"


def test_delayed_morning_run_after_close_skips():
    result = evaluate("OPEN", at=when(2026, 11, 11, 17, 19))
    assert not result["can_scan"]
    assert result["market_status"] == "AFTER_CLOSE"


def test_actual_open_trading_day_is_allowed():
    assert require_allowed("OPEN", at=when(2026, 11, 11, 9, 30))["can_scan"]


def test_official_regular_close_is_1530_not_1540():
    assert not evaluate("OPEN", at=when(2026, 11, 11, 15, 30))["can_scan"]


def test_eod_catchup_on_trading_day_is_allowed():
    assert require_allowed("EOD", at=when(2026, 11, 11, 16, 15))["can_scan"]


def test_unknown_calendar_year_fails_closed():
    assert not evaluate("OPEN", at=when(2027, 1, 5, 9, 30))["can_scan"]


def test_weekend_and_nonpublishing_closed_session_skip():
    assert not evaluate("OPEN", at=when(2026, 11, 14, 9, 30))["can_scan"]
    assert not evaluate("CLOSED", at=when(2026, 11, 11, 9, 30))["can_scan"]


def test_source_timestamp_fails_before_sink_publication():
    now = dt.datetime(2026, 11, 11, 4, 0, tzinfo=dt.timezone.utc)
    meta = {"run_id": "test", "git_sha": "abc", "cycle_id": "cycle", "data_freshness_status": "EXCHANGE_VERIFIED"}
    stale = (now - dt.timedelta(hours=10)).isoformat()
    with pytest.raises(ValueError, match="out of range"):
        validate(stale, "test", "abc", "cycle", "OPEN", expected=meta, now=now)

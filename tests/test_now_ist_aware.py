"""CDX-05 regression: scanner time helpers are timezone-aware and comparable."""
import datetime
from types import SimpleNamespace

import gspread
import pytest

import scanner

IST = scanner.IST


def _book(value):
    cell = SimpleNamespace(value=value)
    ws = SimpleNamespace(acell=lambda addr: cell)
    return SimpleNamespace(worksheet=lambda name: ws)


def test_now_ist_is_aware_and_ist():
    now = scanner.now_ist()
    assert now.tzinfo is not None
    assert now.utcoffset() == datetime.timedelta(hours=5, minutes=30)


def test_now_ist_comparable_with_engine_aware_datetimes():
    import angel_prediction_engine as engine
    assert isinstance(scanner.now_ist() - engine.get_ist_time(), datetime.timedelta)


def test_parse_sheet_ist_aware_and_tolerant():
    parsed = scanner.parse_sheet_ist("2026-10-14 09:15:30")
    assert parsed.tzinfo is not None and parsed.hour == 9
    assert scanner.parse_sheet_ist("2026-10-14 09:15:30 IST") == parsed
    assert scanner.parse_sheet_ist("garbage") is None
    assert scanner.parse_sheet_ist(None) is None


def test_outage_gap_subtraction_no_longer_raises():
    # scanner.run_angel_loop subtracts a parsed sheet value from now_ist()
    now = scanner.now_ist()
    last = scanner.parse_sheet_ist((now - datetime.timedelta(seconds=400)).strftime("%Y-%m-%d %H:%M:%S"))
    assert 395 <= (now - last).total_seconds() <= 405


def test_heartbeat_age_with_aware_now():
    now = datetime.datetime(2026, 10, 14, 10, 0, 30, tzinfo=IST)
    assert scanner.heartbeat_age_seconds(_book("2026-10-14 10:00:00"), now) == 30.0


def test_heartbeat_age_with_naive_now_is_treated_as_ist():
    now = datetime.datetime(2026, 10, 14, 10, 0, 30)
    assert scanner.heartbeat_age_seconds(_book("2026-10-14 10:00:00"), now) == 30.0


def test_heartbeat_age_default_now_and_clamped_at_zero():
    future = (scanner.now_ist() + datetime.timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    assert scanner.heartbeat_age_seconds(_book(future)) == 0.0


@pytest.mark.parametrize("value", [None, "", "not a time"])
def test_heartbeat_age_unreadable_is_none(value):
    assert scanner.heartbeat_age_seconds(_book(value), scanner.now_ist()) is None


def test_heartbeat_age_missing_tab_is_none():
    def _raise(name):
        raise gspread.WorksheetNotFound(name)
    assert scanner.heartbeat_age_seconds(SimpleNamespace(worksheet=_raise), scanner.now_ist()) is None

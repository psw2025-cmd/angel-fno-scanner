"""Regression for 2026-10-26 delayed EOD scheduled run #40364391252."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.scheduled_cycle_gate import ScheduleBlocked, evaluate

OPEN = "45 3 * * 1-5"
EOD = "45 10 * * 1-5"


def day_open(day):
    return {"market_closed": False, "date_ist": day.isoformat()}


def day_closed(day):
    return {"market_closed": True, "date_ist": day.isoformat()}


def clock(hour, minute, *, day=26):
    return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)


def expect_block(schedule, now, code, calendar=day_open):
    with pytest.raises(ScheduleBlocked) as error:
        evaluate(schedule, now=now, calendar=calendar)
    assert error.value.code == code


def test_open_at_0915_ist_allows_only_preflight():
    # 03:45 UTC is 09:15 IST.
    assert evaluate(OPEN, now=clock(3, 45), calendar=day_open)["status"] == "ALLOW_PRE_BROKER_PREFLIGHT_ONLY"


def test_open_at_0945_ist_boundary_allows_preflight():
    assert evaluate(OPEN, now=clock(4, 15), calendar=day_open)["market_session"] == "OPEN"


def test_open_before_0915_ist_blocks():
    expect_block(OPEN, clock(3, 44), "DELAYED_OR_OUTSIDE_WINDOW")


def test_open_after_0945_ist_blocks():
    expect_block(OPEN, clock(4, 16), "DELAYED_OR_OUTSIDE_WINDOW")


def test_eod_at_1615_ist_allows_preflight():
    assert evaluate(EOD, now=clock(10, 45), calendar=day_open)["market_session"] == "EOD"


def test_eod_at_1715_ist_boundary_allows_preflight():
    assert evaluate(EOD, now=clock(11, 45), calendar=day_open)["market_session"] == "EOD"


def test_eod_before_1615_ist_blocks():
    expect_block(EOD, clock(10, 44), "DELAYED_OR_OUTSIDE_WINDOW")


def test_observed_eod_2229_ist_is_blocked_before_broker():
    # Actual failed run #40364391252 started 2026-10-26T16:59:32Z.
    expect_block(EOD, clock(16, 59), "DELAYED_OR_OUTSIDE_WINDOW")


def test_market_holiday_blocks_even_inside_window():
    expect_block(EOD, clock(10, 45), "MARKET_CLOSED", day_closed)


def test_weekend_blocks_even_inside_window():
    expect_block(OPEN, clock(3, 45, day=25), "MARKET_CLOSED", day_closed)


def test_unrecognized_schedule_fails_closed():
    expect_block("45 12 * * 1-5", clock(10, 45), "UNKNOWN_SCHEDULE")


def test_missing_schedule_fails_closed():
    expect_block("", clock(10, 45), "UNKNOWN_SCHEDULE")


def test_naive_clock_fails_closed():
    expect_block(EOD, datetime(2026, 10, 26, 10, 45), "UNTRUSTED_CLOCK")


def test_calendar_failure_fails_closed():
    def bad_calendar(_):
        raise RuntimeError("unknown year")
    expect_block(EOD, clock(10, 45), "CALENDAR_UNAVAILABLE", bad_calendar)


def test_workflow_guards_before_dependency_and_broker_calls():
    path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "market_bot.yml"
    workflow = path.read_text(encoding="utf-8")
    gate = workflow.index("Fail closed on delayed scheduled PAPER scan")
    assert workflow.index("Checkout Code") < gate < workflow.index("Install Libraries")
    assert gate < workflow.index("Run Single Authoritative Scanner")
    assert "if: github.event_name == 'schedule'" in workflow
    assert "SCHEDULE_CRON: ${{ github.event.schedule }}" in workflow
    assert 'python tools/scheduled_cycle_gate.py --schedule "$SCHEDULE_CRON"' in workflow
    assert "REAL_BROKER_ORDERS: '0'" in workflow
    assert workflow.count('test "$REAL_BROKER_ORDERS" = 0') >= 2

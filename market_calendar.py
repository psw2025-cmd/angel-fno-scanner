"""Reviewed regular NSE equity-derivatives calendar; unknown years fail closed.

Source verified 2026-10-03:
https://www.nseindia.com/resources/exchange-communication-holidays
Includes the subsequently announced Maharashtra election holiday. Special
Muhurat sessions require a separately reviewed session window, never a guess.

This file is the only holiday list. Health checks and agents must call
market_session_state() before treating a missing scanner or today's row count
as a failure. That is a failure only when status is OPEN.
"""
import datetime as dt
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
NSE_HOLIDAYS_2026 = frozenset({
    "2026-01-15", "2026-01-26", "2026-03-03", "2026-03-26", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-05-01", "2026-05-28", "2026-06-26",
    "2026-09-14", "2026-10-02", "2026-10-20", "2026-11-10", "2026-11-24", "2026-12-25",
})
# Names are recorded only where the exchange notice or an in-repo source names the day.
# Every other date in NSE_HOLIDAYS_2026 is still a full equity and F&O closure.
NSE_HOLIDAY_NAMES = {
    "2026-10-02": "Mahatma Gandhi Jayanti",
    "2026-10-20": "Dussehra",
    "2026-11-10": "Diwali Balipratipada",
    "2026-11-24": "Guru Nanak Jayanti",
    "2026-12-25": "Christmas",
}


def local_market_time(now):
    return now.astimezone(IST) if now.tzinfo is not None else now.replace(tzinfo=IST)


def is_trading_day(now):
    local = local_market_time(now)
    if local.year != 2026:
        raise RuntimeError("NSE calendar year is unreviewed; refresh the official calendar")
    return local.weekday() < 5 and local.date().isoformat() not in NSE_HOLIDAYS_2026


def session_closure(now=None):
    """None on an open weekday. HOLIDAY or WEEKEND when no equity/F&O session is due."""
    now = now or dt.datetime.now(IST)
    local = local_market_time(now)
    key = local.date().isoformat()
    if local.year != 2026:
        return {
            "status": "UNKNOWN",
            "date": key,
            "name": "",
            "expect_live_scanner": False,
            "expect_fresh_rows": False,
            "summary": "NSE calendar year is unreviewed; refresh the official calendar",
        }
    if key in NSE_HOLIDAYS_2026:
        name = NSE_HOLIDAY_NAMES.get(key, "NSE holiday")
        return {
            "status": "HOLIDAY",
            "date": key,
            "name": name,
            "expect_live_scanner": False,
            "expect_fresh_rows": False,
            "summary": key + " " + name + ": NSE equity and F&O are closed. A missing scanner is expected.",
        }
    if local.weekday() >= 5:
        return {
            "status": "WEEKEND",
            "date": key,
            "name": "weekend",
            "expect_live_scanner": False,
            "expect_fresh_rows": False,
            "summary": key + " weekend: NSE equity and F&O are closed. A missing scanner is expected.",
        }
    return None


def market_session_state(now=None):
    """One answer for holiday, weekend, night, and the live 09:15-15:40 IST session.

    expect_live_scanner is True only while the NSE equity and F&O session is open.
    Night, pre-open, after close, weekends, and holidays are not system failures.
    """
    now = now or dt.datetime.now(IST)
    closure = session_closure(now)
    if closure:
        return closure
    local = local_market_time(now)
    mins = local.hour * 60 + local.minute
    key = local.date().isoformat()
    if mins < (9 * 60 + 15):
        return {
            "status": "BEFORE_OPEN",
            "date": key,
            "name": "before 09:15 IST",
            "expect_live_scanner": False,
            "expect_fresh_rows": False,
            "summary": key + " before 09:15 IST. The NSE session has not started. A missing scanner is expected.",
        }
    if mins > (15 * 60 + 40):
        return {
            "status": "AFTER_CLOSE",
            "date": key,
            "name": "after 15:40 IST",
            "expect_live_scanner": False,
            "expect_fresh_rows": False,
            "summary": key + " after 15:40 IST. The NSE session is over. Overnight silence is not a system failure.",
        }
    return {
        "status": "OPEN",
        "date": key,
        "name": "09:15-15:40 IST",
        "expect_live_scanner": True,
        "expect_fresh_rows": True,
        "summary": key + " NSE session is open, 09:15-15:40 IST. A missing scanner or stale rows needs a real check.",
    }

"""Reviewed regular NSE equity-derivatives calendar; unknown years fail closed.

Source verified 2026-10-03:
https://www.nseindia.com/resources/exchange-communication-holidays
Includes the subsequently announced Maharashtra election holiday. Special
Muhurat sessions require a separately reviewed session window, never a guess.

This file is the only holiday list. One minute on the India clock has one answer.
"""
import datetime as dt
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
NSE_HOLIDAYS_2026 = frozenset({
    "2026-01-15", "2026-01-26", "2026-03-03", "2026-03-26", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-05-01", "2026-05-28", "2026-06-26",
    "2026-09-14", "2026-10-02", "2026-10-20", "2026-11-10", "2026-11-24", "2026-12-25",
})
NSE_HOLIDAY_NAMES = {
    "2026-10-02": "Mahatma Gandhi Jayanti",
    "2026-10-20": "Dussehra",
    "2026-11-10": "Diwali Balipratipada",
    "2026-11-24": "Guru Nanak Jayanti",
    "2026-12-25": "Christmas",
}
OPEN_START = 9 * 60 + 15
OPEN_SCORE_END = 9 * 60 + 45
PRE_CLOSE_START = 15 * 60
CLOSE_END = 15 * 60 + 40


def local_market_time(now):
    return now.astimezone(IST) if now.tzinfo is not None else now.replace(tzinfo=IST)


def is_trading_day(now):
    local = local_market_time(now)
    if local.year != 2026:
        raise RuntimeError("NSE calendar year is unreviewed; refresh the official calendar")
    return local.weekday() < 5 and local.date().isoformat() not in NSE_HOLIDAYS_2026


def session_closure(now=None):
    """None on a weekday that can trade. HOLIDAY, WEEKEND, or UNKNOWN otherwise."""
    now = now or dt.datetime.now(IST)
    local = local_market_time(now)
    key = local.date().isoformat()
    minute = local.hour * 60 + local.minute
    if local.year != 2026:
        return {
            "status": "UNKNOWN",
            "phase": "UNREVIEWED_YEAR",
            "minute_of_day": minute,
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
            "phase": "CLOSED",
            "minute_of_day": minute,
            "date": key,
            "name": name,
            "expect_live_scanner": False,
            "expect_fresh_rows": False,
            "summary": key + " " + name + ": NSE equity and F&O are closed. A missing scanner is expected.",
        }
    if local.weekday() >= 5:
        return {
            "status": "WEEKEND",
            "phase": "CLOSED",
            "minute_of_day": minute,
            "date": key,
            "name": "weekend",
            "expect_live_scanner": False,
            "expect_fresh_rows": False,
            "summary": key + " weekend: NSE equity and F&O are closed. A missing scanner is expected.",
        }
    return None


def market_session_state(now=None):
    """One answer for each minute: holiday, weekend, before open, opening score, session, pre-close, after close.

    The live session is 09:15 through 15:40 IST. 15:40 is still open. 15:41 is after close.
    """
    now = now or dt.datetime.now(IST)
    closure = session_closure(now)
    if closure:
        return closure
    local = local_market_time(now)
    mins = local.hour * 60 + local.minute
    key = local.date().isoformat()
    base = {
        "minute_of_day": mins,
        "date": key,
        "expect_live_scanner": False,
        "expect_fresh_rows": False,
    }
    if mins < OPEN_START:
        return {
            **base,
            "status": "BEFORE_OPEN",
            "phase": "BEFORE_OPEN",
            "name": "before 09:15 IST",
            "summary": key + " before 09:15 IST. The NSE session has not started. A missing scanner is expected.",
        }
    if mins <= OPEN_SCORE_END:
        return {
            **base,
            "status": "OPEN",
            "phase": "OPENING_SCORE",
            "name": "09:15-09:45 IST",
            "expect_live_scanner": True,
            "expect_fresh_rows": True,
            "summary": key + " opening score window, 09:15-09:45 IST.",
        }
    if mins < PRE_CLOSE_START:
        return {
            **base,
            "status": "OPEN",
            "phase": "SESSION",
            "name": "09:46-14:59 IST",
            "expect_live_scanner": True,
            "expect_fresh_rows": True,
            "summary": key + " NSE session is open.",
        }
    if mins <= CLOSE_END:
        return {
            **base,
            "status": "OPEN",
            "phase": "PRE_CLOSE",
            "name": "15:00-15:40 IST",
            "expect_live_scanner": True,
            "expect_fresh_rows": True,
            "summary": key + " pre-close window, 15:00-15:40 IST. Advance picks for the next session are written here.",
        }
    return {
        **base,
        "status": "AFTER_CLOSE",
        "phase": "AFTER_CLOSE",
        "name": "after 15:40 IST",
        "summary": key + " after 15:40 IST. The NSE session is over. Overnight silence is not a system failure.",
    }


def session_day_rows(year=2026):
    """One row per calendar day. Trading days stay TRADING; the minute phase is separate.

    A year other than 2026 raises. Do not invent the next holiday list.
    """
    if year != 2026:
        raise RuntimeError("NSE calendar year is unreviewed; refresh the official calendar")
    day = dt.date(year, 1, 1)
    end = dt.date(year, 12, 31)
    rows = []
    while day <= end:
        state = market_session_state(dt.datetime(day.year, day.month, day.day, 12, 0))
        if state["status"] in ("HOLIDAY", "WEEKEND", "UNKNOWN"):
            day_status = state["status"]
            name = state["name"]
        else:
            day_status = "TRADING"
            name = ""
        rows.append({
            "session_date": day.isoformat(),
            "day_status": day_status,
            "name": name,
            "open_start_minute": OPEN_START,
            "open_score_end_minute": OPEN_SCORE_END,
            "pre_close_start_minute": PRE_CLOSE_START,
            "close_end_minute": CLOSE_END,
        })
        day += dt.timedelta(days=1)
    return rows

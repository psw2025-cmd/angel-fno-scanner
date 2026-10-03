"""Reviewed regular NSE equity-derivatives calendar; unknown years fail closed.

Source verified 2026-10-03:
https://www.nseindia.com/resources/exchange-communication-holidays
Includes the subsequently announced Maharashtra election holiday. Special
Muhurat sessions require a separately reviewed session window, never a guess.
"""
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
NSE_HOLIDAYS_2026 = frozenset({
    "2026-01-15", "2026-01-26", "2026-03-03", "2026-03-26", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-05-01", "2026-05-28", "2026-06-26",
    "2026-09-14", "2026-10-02", "2026-10-20", "2026-11-10", "2026-11-24", "2026-12-25",
})


def local_market_time(now):
    return now.astimezone(IST) if now.tzinfo is not None else now.replace(tzinfo=IST)


def is_trading_day(now):
    local = local_market_time(now)
    if local.year != 2026:
        raise RuntimeError("NSE calendar year is unreviewed; refresh the official calendar")
    return local.weekday() < 5 and local.date().isoformat() not in NSE_HOLIDAYS_2026

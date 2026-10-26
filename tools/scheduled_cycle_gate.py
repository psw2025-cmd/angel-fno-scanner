"""Fail closed before a delayed scheduled PAPER scan can contact broker or publish.

GitHub's schedule event does not expose its intended fire date. This guard checks
actual IST execution time against the reviewed schedule window; it cannot attest
the original scheduled instant or certify any market data.
"""
import argparse
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from nse_calendar import trading_status

IST = ZoneInfo("Asia/Kolkata")
WINDOWS = {
    "45 3 * * 1-5": (9 * 60 + 15, 9 * 60 + 45, "OPEN"),
    "45 10 * * 1-5": (16 * 60 + 15, 17 * 60 + 15, "EOD"),
}


class ScheduleBlocked(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def evaluate(schedule, *, now=None, calendar=trading_status):
    if schedule not in WINDOWS:
        raise ScheduleBlocked("UNKNOWN_SCHEDULE", "unreviewed or missing schedule cron")
    instant = now if now is not None else datetime.now(IST)
    if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
        raise ScheduleBlocked("UNTRUSTED_CLOCK", "timezone-aware clock required")
    local = instant.astimezone(IST)
    try:
        day = calendar(local.date())
    except (RuntimeError, ValueError, OSError, KeyError, TypeError) as exc:
        raise ScheduleBlocked("CALENDAR_UNAVAILABLE", "verified market calendar unavailable") from exc
    if not isinstance(day, dict) or day.get("market_closed") is not False:
        raise ScheduleBlocked("MARKET_CLOSED", "calendar does not authorize a regular trading session")
    start, end, session = WINDOWS[schedule]
    minute = local.hour * 60 + local.minute
    if not start <= minute <= end:
        raise ScheduleBlocked(
            "DELAYED_OR_OUTSIDE_WINDOW",
            f"{session} execution outside reviewed IST window {start // 60:02d}:{start % 60:02d}-"
            f"{end // 60:02d}:{end % 60:02d}",
        )
    return {
        "status": "ALLOW_PRE_BROKER_PREFLIGHT_ONLY",
        "market_session": session,
        "now_ist": local.isoformat(),
        "calendar_date": day.get("date_ist", local.date().isoformat()),
        "schedule": schedule,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(evaluate(args.schedule), sort_keys=True))
        return 0
    except ScheduleBlocked as exc:
        print(json.dumps({"status": "BLOCKED", "code": exc.code, "reason": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Bound scheduled scanner phases below GitHub's six-hour hosted-job limit.

Naive datetimes follow the scanner's existing IST convention. These windows
govern job lifetime; the market calendar and quote freshness remain separate.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo
import sys

IST = ZoneInfo("Asia/Kolkata")
WINDOW_ENDS = {"morning": time(12, 30), "afternoon": time(15, 55)}


def session_deadline(now, window):
    if window == "once":
        return None
    if window not in WINDOW_ENDS:
        raise ValueError("Unknown scanner window")
    local = now.astimezone(IST) if now.tzinfo else now
    end = datetime.combine(local.date(), WINDOW_ENDS[window], tzinfo=local.tzinfo)
    return end.astimezone(now.tzinfo) if now.tzinfo else end


def window_is_active(now, window):
    deadline = session_deadline(now, window)
    local = now.astimezone(IST) if now.tzinfo else now
    return deadline is None or (local.weekday() < 5 and now < deadline)


def wait_seconds_to_open(now, window):
    # The 09:10 cron must wait for 09:15 instead of exiting after one stale pass.
    if window == "once" or not window_is_active(now, window):
        return 0
    local = now.astimezone(IST) if now.tzinfo else now
    opening = local.replace(hour=9, minute=15, second=0, microsecond=0)
    return max(0, (opening - local).total_seconds())


if __name__ == "__main__":
    active = window_is_active(datetime.now(IST), sys.argv[1])
    print("active=" + str(active).lower())

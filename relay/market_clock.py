"""Fail-closed market-hours preflight for PAPER-only live probe."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def market_preflight(now=None):
    now = now or datetime.now(IST)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware clock required")
    local = now.astimezone(IST)
    print("PREFLIGHT_IST_TIME: " + local.isoformat(), flush=True)
    if local.weekday() >= 5 or not (time(9, 15) < local.time().replace(tzinfo=None) <= time(15, 30)):
        print("ABORT: Market is currently closed. Cannot verify live ticks.", flush=True)
        raise SystemExit(2)
    print("PASS: IST weekday market-hours gate", flush=True)
    return local

if __name__ == "__main__":
    market_preflight()

"""Fail-closed NSE market-session preflight for scheduled PAPER publication.

A skipped holiday/delayed scan is not a successful market data publication.
No broker access, lease acquisition or external sink writes occur here.
"""
import argparse
import datetime as dt
import os
from market_calendar import IST, local_market_time, market_session_state

OPEN_MINUTE = 9 * 60 + 15
CLOSE_MINUTE = 15 * 60 + 30


def evaluate(requested, *, at=None):
    if requested not in ("OPEN", "EOD", "CLOSED"):
        raise ValueError("unsupported requested market session")
    instant = local_market_time(at or dt.datetime.now(IST))
    market = market_session_state(instant)
    minute = instant.hour * 60 + instant.minute
    if market["status"] in ("HOLIDAY", "WEEKEND", "UNKNOWN"):
        permitted = False
    elif requested == "OPEN":
        permitted = market["status"] == "OPEN" and OPEN_MINUTE <= minute < CLOSE_MINUTE
    elif requested == "EOD":
        permitted = minute >= CLOSE_MINUTE
    else:
        permitted = False
    return {
        "can_scan": permitted,
        "market_status": market["status"],
        "requested": requested,
        "session_date": instant.date().isoformat(),
        "reason": ("SESSION_ACCEPTED" if permitted else
                   f"PAPER_SCAN_SUPPRESSED:{market['status']}:{requested}"),
    }


def require_allowed(requested, *, at=None):
    result = evaluate(requested, at=at)
    if not result["can_scan"]:
        raise RuntimeError(result["reason"])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requested", choices=("OPEN", "EOD", "CLOSED"), required=True)
    parser.add_argument("--github-output")
    args = parser.parse_args(argv)
    result = evaluate(args.requested)
    print(f"{result['reason']} date={result['session_date']}", flush=True)
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as out:
            out.write(f"can_scan={'true' if result['can_scan'] else 'false'}\n")
            out.write(f"market_status={result['market_status']}\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write(f"\nPAPER market scan: {result['reason']} ({result['session_date']}). "
                      "SKIPPED is not a fresh-data PASS. Real orders disabled.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

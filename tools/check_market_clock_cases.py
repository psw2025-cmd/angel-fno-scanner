"""Five fixed NSE clock cases. Prints PASS or FAIL. Does not trade or write predictions."""
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import market_calendar

IST = ZoneInfo("Asia/Kolkata")
CASES = (
    ("Dussehra 20 Oct 2026 22:00", dt.datetime(2026, 10, 20, 22, 0, tzinfo=IST), "HOLIDAY"),
    ("21 Oct 2026 02:00", dt.datetime(2026, 10, 21, 2, 0, tzinfo=IST), "BEFORE_OPEN"),
    ("21 Oct 2026 10:00", dt.datetime(2026, 10, 21, 10, 0, tzinfo=IST), "OPEN"),
    ("21 Oct 2026 22:00", dt.datetime(2026, 10, 21, 22, 0, tzinfo=IST), "AFTER_CLOSE"),
    ("24 Oct 2026 12:00 weekend", dt.datetime(2026, 10, 24, 12, 0, tzinfo=IST), "WEEKEND"),
)
LOG_DIR = Path(r"C:\AngelFNO_Workstation\angel-agent-supervisor\logs")


def run_cases():
    rows = []
    fails = 0
    for label, when, expected in CASES:
        got = market_calendar.market_session_state(when)
        observed = got.get("status")
        ok = observed == expected
        if not ok:
            fails += 1
        rows.append({
            "label": label,
            "when": when.isoformat(),
            "expected": expected,
            "observed": observed,
            "name": got.get("name"),
            "expect_live_scanner": got.get("expect_live_scanner"),
            "summary": got.get("summary"),
            "result": "PASS" if ok else "FAIL",
        })
    return rows, fails


def main():
    started = dt.datetime.now(dt.timezone.utc)
    rows, fails = run_cases()
    overall = "PASS" if fails == 0 else "FAIL"
    lines = [
        "MARKET CLOCK CASES",
        "started_utc=" + started.isoformat(),
        "source=market_calendar.market_session_state",
    ]
    for row in rows:
        lines.append(
            row["result"]
            + " | "
            + row["label"]
            + " | expected="
            + row["expected"]
            + " observed="
            + str(row["observed"])
            + " name="
            + str(row["name"])
        )
        lines.append("  " + str(row["summary"]))
    lines.append("CLOCK_CASES_FAILS=" + str(fails))
    lines.append("RESULT " + overall)
    text = "\n".join(lines) + "\n"
    print(text, end="")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    log_path = LOG_DIR / ("clock_cases_" + stamp + ".txt")
    log_path.write_text(text, encoding="utf-8")
    (LOG_DIR / ("clock_cases_" + stamp + ".json")).write_text(
        json.dumps({"started_utc": started.isoformat(), "overall": overall, "fails": fails, "cases": rows}, indent=2),
        encoding="utf-8",
    )
    print("evidence=" + str(log_path))
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

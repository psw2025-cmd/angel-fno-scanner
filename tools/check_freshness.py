"""Fail-closed freshness and cycle identity validation for snapshot publication."""
import argparse
import datetime as dt
import json
import os
import sys

def validate(source_timestamp, run_id, git_sha, cycle_id, market_session, *, expected=None, now=None):
    if market_session not in ("OPEN", "CLOSED", "EOD"):
        raise ValueError("invalid market session")
    identity = {"run_id": str(run_id), "git_sha": str(git_sha), "cycle_id": str(cycle_id)}
    if not all(identity.values()):
        raise ValueError("missing cycle identity")
    if expected is None or not all(str(expected.get(k, "")) for k in identity):
        raise ValueError("authoritative cycle metadata missing")
    for k, value in identity.items():
        if value != str(expected[k]):
            raise ValueError(f"{k} mismatch")
    try:
        stamp = dt.datetime.fromisoformat(str(source_timestamp).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid source timestamp") from exc
    if stamp.tzinfo is None:
        raise ValueError("source timestamp must include timezone")
    current = now or dt.datetime.now(dt.timezone.utc)
    age = (current - stamp).total_seconds()
    maximum = 120 if market_session == "OPEN" else 86400  # EOD: reject only yesterday-old data
    if age < -30 or age > maximum:
        raise ValueError(f"source timestamp out of range: {age:.0f}s (max {maximum}s)")
    return {"status": "PASS", "age_seconds": round(age), "max_age_seconds": maximum, **identity}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata", help="authoritative JSON with exchange-verified source timestamp")
    p.add_argument("--source-timestamp")
    p.add_argument("--run-id")
    p.add_argument("--git-sha")
    p.add_argument("--cycle-id")
    p.add_argument("--market-session", choices=("OPEN", "CLOSED", "EOD"), required=True)
    p.add_argument("--expected-metadata", help="JSON file from authoritative cycle metadata")
    a = p.parse_args(argv)
    try:
        path = a.metadata or a.expected_metadata
        if not path:
            raise ValueError("authoritative metadata path required")
        with open(path, encoding="utf-8") as f:
            expected = json.load(f)
        if a.metadata and expected.get("data_freshness_status") != "EXCHANGE_VERIFIED":
            raise ValueError("exchange timestamp not verified")
        print(json.dumps(validate(a.source_timestamp or expected.get("source_timestamp"),
            a.run_id or expected.get("run_id"), a.git_sha or expected.get("git_sha"),
            a.cycle_id or expected.get("cycle_id"),
            a.market_session or expected.get("market_session"), expected=expected)))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"FAIL CLOSED: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())

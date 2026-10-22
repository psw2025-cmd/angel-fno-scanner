#!/usr/bin/env python3
"""Fail closed on incomplete NASA evidence, without suppressing artifact upload.

This is a ledger-integrity gate, not independent proof of cloud readiness.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys

EXPECTED_IDS = {f"P-{n:02d}" for n in range(1, 26)}
STATUSES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")


def evaluate_ledger(payload, expected_sha, now=None):
    errors = []
    if not isinstance(payload, dict):
        return ["ledger_not_object"]
    now = now or datetime.now(timezone.utc)
    if not re.fullmatch(r"[0-9a-f]{40}", expected_sha or ""):
        errors.append("invalid_expected_sha")
    generated = payload.get("generated_at_utc")
    try:
        generated_dt = datetime.fromisoformat(generated)
        if generated_dt.tzinfo is None:
            raise ValueError("naive timestamp")
        if not (-timedelta(minutes=5) <= now - generated_dt <= timedelta(minutes=60)):
            errors.append("stale_or_future_generated_at")
    except (ValueError, TypeError):
        errors.append("invalid_generated_at")
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return errors + ["checks_not_list"]
    ids = [c.get("id") if isinstance(c, dict) else None for c in checks]
    if len(ids) != len(EXPECTED_IDS) or set(ids) != EXPECTED_IDS:
        errors.append("incomplete_or_duplicate_check_ids")
    counts = {status: 0 for status in STATUSES}
    for c in checks:
        if not isinstance(c, dict):
            errors.append("invalid_check_record")
            continue
        status = c.get("status")
        if status not in counts:
            errors.append(f"invalid_status:{c.get('id')}")
            continue
        counts[status] += 1
        if status != "PASS":
            errors.append(f"unverified:{c.get('id')}:{status}")
        if c.get("source_sha") != expected_sha:
            errors.append(f"source_sha_mismatch:{c.get('id')}")
        if c.get("timestamp") != generated:
            errors.append(f"timestamp_mismatch:{c.get('id')}")
        evidence = c.get("evidence")
        if not isinstance(evidence, dict) or not isinstance(evidence.get("reason"), str) or not evidence["reason"].strip():
            errors.append(f"missing_evidence_reason:{c.get('id')}")
        if status == "PASS" and (not isinstance(evidence, dict) or evidence.get("details") is None):
            errors.append(f"missing_pass_details:{c.get('id')}")
    if payload.get("summary") != counts:
        errors.append("summary_mismatch")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--expect-sha", required=True)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.ledger.read_text(encoding="utf-8"))
        errors = evaluate_ledger(payload, args.expect_sha)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"NASA_LEDGER_FAIL invalid_or_missing_ledger:{type(exc).__name__}")
        return 1
    if errors:
        print("NASA_LEDGER_FAIL " + json.dumps(errors, sort_keys=True))
        return 1
    print("NASA_LEDGER_PASS all_25_checks_complete_current_sha_with_evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main())

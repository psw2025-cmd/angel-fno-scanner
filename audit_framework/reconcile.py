"""Deterministic, offline, fail-closed evidence reconciliation.

This is not an AI-agent launcher, broker client or live-market certification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

STATUSES = frozenset({"PASS", "FAIL", "BLOCKED", "UNKNOWN"})
REQUIRED = frozenset({"check_id", "status", "source_sha", "run_id", "artifact_sha256"})


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(receipts: list[dict], required_ids: list[str], expected_sha: str) -> dict:
    """Reject missing, duplicated, conflicting or unevidenced mandatory receipts."""
    result = {"status": "FAIL", "gates": {}, "errors": []}
    if not isinstance(expected_sha, str) or len(expected_sha) != 40 or any(c not in "0123456789abcdefABCDEF" for c in expected_sha):
        result["errors"].append("invalid_expected_sha")
    if not isinstance(receipts, list) or not isinstance(required_ids, list) or not required_ids or len(required_ids) != len(set(required_ids)):
        result["errors"].append("invalid_inputs")
        return result
    seen = {}
    for index, receipt in enumerate(receipts):
        if not isinstance(receipt, dict) or not REQUIRED.issubset(receipt):
            result["errors"].append(f"malformed_receipt:{index}")
            continue
        key = receipt["check_id"]
        if not isinstance(key, str) or not key:
            result["errors"].append(f"invalid_check_id:{index}")
            continue
        if key in seen:
            result["errors"].append(f"duplicate_check_id:{key}")
        seen[key] = receipt
    for key in required_ids:
        r = seen.get(key)
        if r is None:
            result["gates"][key] = "BLOCKED"
            result["errors"].append(f"missing:{key}")
            continue
        status = r["status"]
        digest = r["artifact_sha256"]
        valid = (status in STATUSES and r["source_sha"] == expected_sha
                 and isinstance(r["run_id"], str) and bool(r["run_id"].strip())
                 and isinstance(digest, str) and len(digest) == 64
                 and all(c in "0123456789abcdefABCDEF" for c in digest))
        if not valid:
            result["gates"][key] = "FAIL"
            result["errors"].append(f"invalid_evidence:{key}")
        else:
            result["gates"][key] = status
            if status != "PASS":
                result["errors"].append(f"not_pass:{key}:{status}")
    result["status"] = "PASS" if not result["errors"] else "FAIL"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipts = json.loads(args.receipts.read_text(encoding="utf-8"))
        contract = json.loads(args.contract.read_text(encoding="utf-8"))
        report = assess(receipts, contract["required_ids"], contract["source_sha"])
    except (OSError, ValueError, TypeError, KeyError) as exc:
        report = {"status": "FAIL", "gates": {}, "errors": ["input_error:" + type(exc).__name__]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

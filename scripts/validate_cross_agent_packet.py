#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ALLOWED = {
    "OBSERVED","OPEN_AUTO_FIXABLE","IMPLEMENTED_NOT_DEPLOYED","VERIFIED_LOCAL",
    "VERIFIED_REMOTE","DISPUTED","WAITING_FOR_PEER","WAITING_FOR_USER",
    "RESOLVED_TWO_PARTY",
}
REQUIRED = {
    "claim_id","claiming_agent","claim_time_ist","host_or_runtime","repo",
    "claim","observation","primary_evidence","before_state","action_taken",
    "after_state","safety_state","secrets_redacted","peer_check_request","status",
}

def validate(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    missing = sorted(REQUIRED - set(data))
    if missing:
        errors.append("missing fields: " + ", ".join(missing))
    if data.get("repo") != "psw2025-cmd/angel-fno-scanner":
        errors.append("wrong repo")
    if data.get("status") not in ALLOWED:
        errors.append("invalid status")
    if data.get("secrets_redacted") is not True:
        errors.append("secrets_redacted must be true")
    if not str(data.get("claim_id", "")).strip():
        errors.append("claim_id empty")
    return errors

def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_cross_agent_packet.py <packet.json>")
        return 2
    path = Path(sys.argv[1])
    try:
        errors = validate(path)
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1
    if errors:
        print("FAIL:")
        for e in errors:
            print(f" - {e}")
        return 1
    print("PASS: cross-agent packet structure valid")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

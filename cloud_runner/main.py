"""Cloud PAPER orchestration, delegating calculation to reviewed Phase 2 code."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cloud_runner.session import validate_environment, REQUIRED
from cloud_runner.health import snapshot

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "proof-output" / "cloud-paper"

def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()

def exact_paper_flags(data):
    """JSON safety flags must be integer 1/0, never Python bool equivalents."""
    return (type(data.get("paper_mode")) is int
            and data["paper_mode"] == 1
            and type(data.get("live_order_authority")) is int
            and data["live_order_authority"] == 0)

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--once", action="store_true")
    args = parser.parse_args()
    validate_environment()
    if args.preflight:
        print(json.dumps(snapshot(), sort_keys=True))
        return 0
    runtime = Path(os.environ.get("CLOUD_PAPER_RUNTIME_DIR", "")).resolve()
    if not runtime.is_dir() or git(runtime, "branch", "--show-current") != "test-framework":
        raise RuntimeError("WRITE_GUARD: separate test-framework checkout required")
    # Prevent the child writer from overriding inherited fail-closed flags via .env.
    if (runtime / ".env").exists():
        raise RuntimeError("UNREVIEWED_ENV_FILE_IN_CHILD_RUNTIME")
    # A tracked or prior-session receipt is never proof that this invocation ran.
    source = runtime / "data" / "paper_ledger" / "receipt.json"
    before_receipt = source.read_bytes() if source.is_file() else None
    started_at = datetime.now(timezone.utc)
    PROOF.mkdir(parents=True, exist_ok=True)
    (PROOF / "status.json").write_text(json.dumps({
        "status": "RUNNING_NOT_VERIFIED", "paper_mode": 1,
        "live_order_authority": 0, "real_broker_orders": 0,
        "broker_order_audit": "NOT_PERFORMED"
    }, sort_keys=True) + "\n", encoding="utf-8")
    # The writer itself retains all its existing branch, broker and PAPER gates.
    env = dict(os.environ, PAPER_MODE="1", LIVE_ORDER_AUTHORITY="0",
               REAL_BROKER_ORDERS="0", PAPER_LEDGER_BRANCH="test-framework")
    result = subprocess.run([sys.executable, "run_phase2_local.py"],
                            cwd=runtime, env=env, check=False)
    if result.returncode:
        (PROOF / "status.json").write_text(json.dumps({
            "status": "FAIL_CLOSED", "error_type": "CHILD_EXIT_NONZERO",
            "child_exit_code": result.returncode,
            "broker_order_audit": "NOT_PERFORMED"
        }, sort_keys=True) + "\n", encoding="utf-8")
        return result.returncode
    if not source.is_file():
        raise RuntimeError("RECEIPT_MISSING")
    if before_receipt is not None and source.read_bytes() == before_receipt:
        raise RuntimeError("RECEIPT_NOT_REFRESHED")
    receipt = json.loads(source.read_text(encoding="utf-8"))
    if (not exact_paper_flags(receipt)
            or receipt.get("status") != "LOCAL_ARTIFACT_ONLY_NOT_INSERTED"):
        raise RuntimeError("RECEIPT_SAFETY_FAILURE")
    from phase2.daily_close import canonical_hash
    payload = json.loads(receipt["bigquery_merge_parameters"]["payload"])
    try:
        issued_at = datetime.fromisoformat(payload["created_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("RECEIPT_TIMESTAMP_INVALID") from exc
    if issued_at.tzinfo is None or issued_at.utcoffset() is None:
        raise RuntimeError("RECEIPT_TIMESTAMP_INVALID")
    if not (started_at <= issued_at.astimezone(timezone.utc)
            <= datetime.now(timezone.utc) + timedelta(seconds=5)):
        raise RuntimeError("RECEIPT_NOT_FROM_CURRENT_RUN")
    # All three artifacts must refer to the same broker snapshot provenance.
    # This is consistency validation, not proof that the snapshot was live.
    source_hash = payload.get("source_hash")
    if (not isinstance(source_hash, str)
            or re.fullmatch(r"[0-9a-f]{64}", source_hash) is None
            or receipt.get("source_hash") != source_hash):
        raise RuntimeError("SOURCE_PROVENANCE_MISMATCH")
    # Bind the signed-off prediction hash to the actual captured broker snapshot
    # bytes. Internal agreement among receipt/entry/DNA alone is insufficient.
    raw = runtime / "data" / "raw_snapshot.json"
    if not raw.is_file():
        raise RuntimeError("RAW_SNAPSHOT_MISSING")
    raw_bytes = raw.read_bytes()
    if hashlib.sha256(raw_bytes).hexdigest() != source_hash:
        raise RuntimeError("RAW_SNAPSHOT_HASH_MISMATCH")
    try:
        raw_snapshot = json.loads(raw_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("RAW_SNAPSHOT_INVALID") from exc
    if (not isinstance(raw_snapshot, dict)
            or raw_snapshot.get("captured_at") != payload.get("source_timestamp")):
        raise RuntimeError("RAW_SNAPSHOT_TIMESTAMP_MISMATCH")
    # Hash equality and timestamp equality alone can certify a replayed snapshot.
    # The Phase 2 child captures its broker snapshot after this invocation starts.
    try:
        source_captured_at = datetime.fromisoformat(raw_snapshot["captured_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("RAW_SNAPSHOT_TIMESTAMP_INVALID") from exc
    if source_captured_at.tzinfo is None or source_captured_at.utcoffset() is None:
        raise RuntimeError("RAW_SNAPSHOT_TIMESTAMP_INVALID")
    if not (started_at <= source_captured_at.astimezone(timezone.utc)
            <= datetime.now(timezone.utc) + timedelta(seconds=5)):
        raise RuntimeError("RAW_SNAPSHOT_NOT_FROM_CURRENT_RUN")
    digest = canonical_hash({k: v for k, v in payload.items() if k != "prediction_hash"})
    if not (digest == receipt["prediction_hash"] == payload["prediction_hash"]
            == receipt["bigquery_merge_parameters"]["hash"]):
        raise RuntimeError("RECEIPT_HASH_FAILURE")
    entry = runtime / "data" / "paper_ledger" / ("entry_" + digest + ".json")
    dna = runtime / "data" / "anomaly_logs" / ("dna_" + digest + ".json")
    if not entry.is_file() or not dna.is_file():
        raise RuntimeError("LINKED_EVIDENCE_MISSING")
    for path in (entry, dna):
        data = json.loads(path.read_text(encoding="utf-8"))
        if (data.get("prediction_hash") != digest
                or data.get("source_hash") != source_hash
                or not exact_paper_flags(data)):
            raise RuntimeError("LINKED_EVIDENCE_INVALID")
    PROOF.mkdir(parents=True, exist_ok=True)
    for path in (source, entry, dna):
        shutil.copyfile(path, PROOF / path.name)
    # Preserve the verified bytes rather than re-reading a mutable source file.
    (PROOF / "raw_snapshot.json").write_bytes(raw_bytes)
    (PROOF / "status.json").write_text(json.dumps({
        "status": "PAPER_RECEIPT_VERIFIED",
        "prediction_hash": digest,
        "runtime_sha": git(runtime, "rev-parse", "HEAD"),
        "paper_mode": 1,
        "live_order_authority": 0,
        "real_broker_orders": 0,
        "broker_order_audit": "NOT_PERFORMED"
    }, sort_keys=True) + "\n", encoding="utf-8")
    print("PAPER_RECEIPT_VERIFIED")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        PROOF.mkdir(parents=True, exist_ok=True)
        (PROOF / "status.json").write_text(json.dumps({"status": "FAIL_CLOSED", "error_type": type(exc).__name__, "missing_snapshot_variable_names": [name for name in REQUIRED[:4] if not os.getenv(name)], "paper_mode": os.getenv("PAPER_MODE") == "1", "live_order_authority": os.getenv("LIVE_ORDER_AUTHORITY") == "0", "real_broker_orders": os.getenv("REAL_BROKER_ORDERS") == "0"}, sort_keys=True) + "\n", encoding="utf-8")
        print("CLOUD_PAPER_RUNNER_FAIL_CLOSED type=" + type(exc).__name__, file=sys.stderr)
        sys.exit(1)

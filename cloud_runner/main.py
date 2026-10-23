"""Cloud PAPER orchestration, delegating calculation to reviewed Phase 2 code."""
import argparse
import json
import os
import shutil
import subprocess
import sys
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
    # The writer itself retains all its existing branch, broker and PAPER gates.
    env = dict(os.environ, PAPER_MODE="1", LIVE_ORDER_AUTHORITY="0",
               REAL_BROKER_ORDERS="0", PAPER_LEDGER_BRANCH="test-framework")
    result = subprocess.run([sys.executable, "run_phase2_local.py"],
                            cwd=runtime, env=env, check=False)
    if result.returncode:
        return result.returncode
    source = runtime / "data" / "paper_ledger" / "receipt.json"
    if not source.is_file():
        raise RuntimeError("RECEIPT_MISSING")
    receipt = json.loads(source.read_text(encoding="utf-8"))
    if (receipt.get("paper_mode") != 1 or receipt.get("live_order_authority") != 0
            or receipt.get("status") != "LOCAL_ARTIFACT_ONLY_NOT_INSERTED"):
        raise RuntimeError("RECEIPT_SAFETY_FAILURE")
    from phase2.daily_close import canonical_hash
    payload = json.loads(receipt["bigquery_merge_parameters"]["payload"])
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
        if data.get("prediction_hash") != digest or data.get("paper_mode") != 1 or data.get("live_order_authority") != 0:
            raise RuntimeError("LINKED_EVIDENCE_INVALID")
    PROOF.mkdir(parents=True, exist_ok=True)
    for path in (source, entry, dna):
        shutil.copyfile(path, PROOF / path.name)
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

"""Cloud entrypoint: reuse existing Phase 2; never duplicate trading calculations."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Accept direct script invocation from the repository root.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cloud_runner.session import validate_environment
from cloud_runner.health import snapshot

ROOT = Path(__file__).resolve().parents[1]

def current_branch():
    return subprocess.run(
        ["git", "branch", "--show-current"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()

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
    # run_phase2_local.py owns the receipt writer and rejects other branches.
    # Never bypass its reviewed test-framework ownership from an isolated PR.
    if current_branch() != "test-framework":
        raise RuntimeError("WRITE_GUARD: --once requires reviewed test-framework runtime")
    env = dict(os.environ, PAPER_MODE="1", LIVE_ORDER_AUTHORITY="0",
               PAPER_LEDGER_BRANCH="test-framework")
    # This existing entrypoint performs read-only authentication, instrument
    # discovery, feature extraction, ranking and receipt generation.
    # No --push here: publication remains with the existing reviewed workflow.
    return subprocess.run(
        [sys.executable, "run_phase2_local.py"], cwd=ROOT, env=env,
        check=False,
    ).returncode

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Deliberately omit untrusted exception detail/SDK response.
        print("CLOUD_PAPER_RUNNER_FAIL_CLOSED type=" + type(exc).__name__,
              file=sys.stderr)
        sys.exit(1)

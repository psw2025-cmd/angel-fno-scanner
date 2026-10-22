"""Regression coverage for the NASA workflow fail-closed ledger gate."""
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/nasa-daily-proof.yml"


def gate_script():
    source = WORKFLOW.read_text(encoding="utf-8")
    block = source.split("      - name: Enforce complete NASA proof ledger", 1)[1].split("      - name: Upload timestamped proof ledger", 1)[0]
    match = re.search(r"python - <<'PY'\\n(.*?)\\n          PY", block, re.S)
    assert match, "NASA gate script missing"
    return "\\n".join(line[10:] if line.startswith("          ") else line for line in match.group(1).splitlines())


def sample():
    return {"checks": [{"id": f"P-{n:02d}", "status": "PASS", "source_sha": "test-sha"} for n in range(1, 21)], "summary": {"PASS": 20, "FAIL": 0, "BLOCKED": 0, "NOT_RUN": 0}}


def invoke(tmp_path, payload):
    target = tmp_path / "proof-output"
    target.mkdir(exist_ok=True)
    (target / "PROVEN_PROOF_LEDGER.json").write_text(json.dumps(payload), encoding="utf-8")
    return subprocess.run([sys.executable, "-c", gate_script()], cwd=tmp_path, env={**os.environ, "GITHUB_SHA": "test-sha"}, capture_output=True, text=True)


def test_complete_ledger_passes(tmp_path):
    assert invoke(tmp_path, sample()).returncode == 0


def test_blocked_fails(tmp_path):
    d = sample(); d["checks"][0]["status"] = "BLOCKED"
    assert invoke(tmp_path, d).returncode != 0


def test_failed_fails(tmp_path):
    d = sample(); d["checks"][0]["status"] = "FAIL"
    assert invoke(tmp_path, d).returncode != 0


def test_missing_fails(tmp_path):
    d = sample(); d["checks"].pop()
    assert invoke(tmp_path, d).returncode != 0


def test_duplicate_fails(tmp_path):
    d = sample(); d["checks"][1]["id"] = d["checks"][0]["id"]
    assert invoke(tmp_path, d).returncode != 0


def test_stale_sha_fails(tmp_path):
    d = sample(); d["checks"][0]["source_sha"] = "previous-run"
    assert invoke(tmp_path, d).returncode != 0


def test_false_summary_fails(tmp_path):
    d = sample(); d["summary"]["PASS"] = 19
    assert invoke(tmp_path, d).returncode != 0

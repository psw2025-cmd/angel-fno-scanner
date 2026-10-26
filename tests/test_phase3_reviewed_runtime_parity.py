"""Offline behavioral guard: Phase 3 must use reviewed main code before broker/PnL work."""
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/phase3-angel-pnl.yml"
REVIEWED_PATHS = (
    "run_phase3_pnl.py",
    "update_phase4_dashboard.py",
    "phase2/angel_readonly.py",
    "phase2/option_stream.py",
    "phase2/option_dna.py",
    "nse_calendar.py",
    "nse_holidays.json",
    "requirements-phase2.txt",
)


def git(where, *args):
    return subprocess.run(
        ["git", *args], cwd=where, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.strip()


def parity_script():
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    marker = "      - name: Verify reviewed Phase 3 runtime parity"
    assert lines.count(marker) == 1
    pos = lines.index(marker)
    assert lines[pos + 1] == "        shell: bash"
    assert lines[pos + 2] == "        run: |"
    body = []
    for line in lines[pos + 3:]:
        if line and not line.startswith("          "):
            break
        body.append(line)
    assert body
    return textwrap.dedent("\n".join(body))


@pytest.fixture
def checkout(tmp_path):
    origin = tmp_path / "origin.git"
    repo = tmp_path / "work"
    git(tmp_path, "init", "--bare", "--initial-branch=main", str(origin))
    git(tmp_path, "clone", str(origin), str(repo))
    git(repo, "config", "user.email", "paper-tests@example.invalid")
    git(repo, "config", "user.name", "Paper CI Test")
    for name in REVIEWED_PATHS:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("reviewed:" + name + "\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "reviewed main runtime")
    git(repo, "push", "origin", "main")
    git(repo, "checkout", "-b", "test-framework")
    ledger = repo / "data/paper_ledger/receipt.json"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text('{"mode":"PAPER"}\n', encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "independent paper ledger data")
    return repo


def run_gate(repo, **overrides):
    env = dict(os.environ)
    env.update(
        GITHUB_REPOSITORY="psw2025-cmd/angel-fno-scanner",
        PAPER_MODE="1", LIVE_ORDER_AUTHORITY="0", REAL_BROKER_ORDERS="0",
    )
    env.update(overrides)
    return subprocess.run(
        ["bash", "-e", "-c", parity_script()], cwd=repo, env=env,
        capture_output=True, text=True, timeout=15,
    )


def test_parity_runs_before_dependencies_broker_and_dashboard():
    source = WORKFLOW.read_text(encoding="utf-8")
    anchor = source.index("- name: Verify reviewed Phase 3 runtime parity")
    assert anchor < source.index("- run: python -m pip install -r requirements-phase2.txt")
    assert anchor < source.index("- name: Run theoretical read-only PnL")
    assert anchor < source.index("- name: Update and push factual paper dashboard")
    for path in REVIEWED_PATHS:
        assert path in parity_script()
    assert "git fetch" in parity_script()
    assert "git hash-object" in parity_script()
    assert "FETCH_HEAD:" in parity_script()
    assert "REAL_BROKER_ORDERS: '0'" in source


def test_matching_reviewed_runtime_with_independent_ledger_passes(checkout):
    assert run_gate(checkout).returncode == 0


@pytest.mark.parametrize("path", [
    "run_phase3_pnl.py", "update_phase4_dashboard.py",
    "phase2/angel_readonly.py", "phase2/option_stream.py",
    "phase2/option_dna.py", "nse_calendar.py", "requirements-phase2.txt",
])
def test_unreviewed_runtime_file_rejected(checkout, path):
    (checkout / path).write_text("UNREVIEWED runtime change\n", encoding="utf-8")
    assert run_gate(checkout).returncode != 0


def test_missing_required_runtime_file_rejected(checkout):
    (checkout / "nse_holidays.json").unlink()
    assert run_gate(checkout).returncode != 0


@pytest.mark.parametrize("key,value", [
    ("PAPER_MODE", "0"),
    ("LIVE_ORDER_AUTHORITY", "1"),
    ("REAL_BROKER_ORDERS", "1"),
    ("GITHUB_REPOSITORY", "other/unsafe-repository"),
])
def test_unsafe_environment_rejected(checkout, key, value):
    assert run_gate(checkout, **{key: value}).returncode != 0


def test_unavailable_remote_main_fails_closed(checkout):
    git(checkout, "remote", "remove", "origin")
    assert run_gate(checkout).returncode != 0

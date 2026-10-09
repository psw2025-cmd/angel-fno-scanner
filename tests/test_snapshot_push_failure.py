"""Regression contract for fail-closed GitHub snapshot publication."""
from pathlib import Path
import re

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/market_bot.yml"

def test_snapshot_push_failure_is_explicit():
    text = WORKFLOW.read_text(encoding="utf-8")
    block = text.split("- name: Commit & Push Updated Snapshots", 1)[1].split("- name: Create Issue on Failure", 1)[0]
    assert "for i in 1 2 3 4 5; do" in block
    assert "git push origin HEAD:main" in block
    assert "pushed=1" in block
    assert 'if [ "$pushed" -ne 1 ]; then' in block
    assert "exit 1" in block
    assert "::error::Snapshot push failed after 5 attempts" in block
    assert "git pull --rebase" not in block
    assert "git push origin main && break || sleep" not in block

def test_snapshot_push_step_fails_closed_when_git_push_fails():
    text = WORKFLOW.read_text(encoding="utf-8")
    block = text.split("- name: Commit & Push Updated Snapshots", 1)[1].split("- name: Create Issue on Failure", 1)[0]
    assert re.search(r"if git push origin HEAD:main; then\s+pushed=1\s+break", block)
    assert re.search(r'if \[ "\$pushed" -ne 1 \]; then\s+echo ".*"\s+exit 1', block)

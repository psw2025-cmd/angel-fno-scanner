"""Encoding CI must attest the PR head SHA on both runner platforms.

Static workflow contract only; an actual GitHub Actions job receipt is
required to establish that the workflow ran at the expected revision.
"""
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/encoding-safety.yml"


def _workflow():
    return WORKFLOW.read_text(encoding="utf-8")


def test_encoding_checkout_targets_pr_head_not_implicit_merge_ref():
    text = _workflow()
    checkout = text.split("- uses: actions/checkout@v4", 1)[1].split(
        "- name: Verify exact source revision", 1
    )[0]
    assert "repository: ${{ github.event.pull_request.head.repo.full_name || github.repository }}" in checkout
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in checkout
    assert "persist-credentials: false" in checkout


def test_encoding_guard_checks_actual_git_sha_and_fails_closed():
    text = _workflow()
    verify = text.split("- name: Verify exact source revision", 1)[1].split(
        "- uses: actions/setup-python@v5", 1
    )[0]
    assert "EXPECTED_HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}" in verify
    assert 'actual="$(git rev-parse HEAD)"' in verify
    assert 'test "$actual" = "$EXPECTED_HEAD_SHA"' in verify
    assert "set -euo pipefail" in verify


def test_encoding_contract_runs_on_both_platforms_without_weakening_scope():
    text = _workflow()
    assert "matrix:" in text
    assert "os: [ubuntu-latest, windows-latest]" in text
    assert "permissions:\n  contents: read" in text
    assert "tests/test_encoding_head_identity_workflow.py" in text
    assert "continue-on-error" not in text

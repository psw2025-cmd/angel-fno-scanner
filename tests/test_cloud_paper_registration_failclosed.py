"""Regression guard: a registration-only workflow must not impersonate a PAPER run.

These checks are structural; they cannot establish cloud deployment, broker data,
or absence of broker orders.
"""
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/cloud-paper-runner.yml"


def _source():
    return WORKFLOW.read_text(encoding="utf-8")


def test_placeholder_fails_closed_instead_of_reporting_registered_success():
    source = _source()
    assert 'echo "Registered"' not in source
    assert "CLOUD_PAPER_NOT_DEPLOYED" in source
    assert "exit 1" in source


def test_placeholder_is_manual_and_read_only():
    source = _source()
    assert "workflow_dispatch" in source
    assert "contents: read" in source
    assert "schedule:" not in source
    assert "push:" not in source


def test_placeholder_cannot_authorize_real_orders():
    source = _source()
    assert "PAPER_MODE: '1'" in source
    assert "LIVE_ORDER_AUTHORITY: '0'" in source
    assert "REAL_BROKER_ORDERS: '0'" in source

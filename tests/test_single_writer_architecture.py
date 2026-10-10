from pathlib import Path
import sys

import pytest

from angel_prediction_engine import news_dedup_key
from scripts import forward_validation as fv
from writer_guard import build_provenance, require_authorized_writer

ROOT = Path(__file__).resolve().parents[1]


def test_writer_guard_fails_closed(monkeypatch):
    monkeypatch.delenv("ALLOW_PRODUCTION_WRITES", raising=False)
    monkeypatch.delenv("WRITER_ID", raising=False)
    with pytest.raises(RuntimeError, match="only market_bot"):
        require_authorized_writer()


def test_writer_guard_emits_consistent_provenance(monkeypatch):
    monkeypatch.setenv("ALLOW_PRODUCTION_WRITES", "1")  # test isolation only - prod code uses conditional 0/1
    monkeypatch.setenv("WRITER_ID", "market_bot")
    monkeypatch.setenv("RUN_ID", "12345")
    monkeypatch.setenv("GIT_SHA", "abc123")
    require_authorized_writer()
    p = build_provenance("2026-10-01 11:45:00")
    assert p == {
        "run_id": "12345",
        "git_sha": "abc123",
        "writer_id": "market_bot",
        "source_timestamp": "2026-10-01 11:45:00",
    }


def test_market_bot_is_single_authorized_writer():
    workflow = (ROOT / ".github/workflows/market_bot.yml").read_text(encoding="utf-8-sig")
    assert workflow.count("python scanner.py") == 1
    assert "angel_prediction_engine.py --run-once" not in workflow
    assert "ALLOW_PRODUCTION_WRITES: ${{ github.event_name == 'schedule' && '1' || (github.event_name == 'workflow_dispatch' && !inputs.dry_run && '1' || '0') }}" in workflow
    assert "if: ${{ github.event_name == 'workflow_dispatch' && inputs.dry_run }}" in workflow
    assert "if: ${{ github.event_name == 'schedule' || (github.event_name == 'workflow_dispatch' && !inputs.dry_run) }}" in workflow
    assert "python tools/probe_angel_live.py --read-only --log-coverage" in workflow
    assert "WRITER_ID: market_bot" in workflow
    assert "RUN_ID: ${{ github.run_id }}" in workflow
    assert "GIT_SHA: ${{ github.sha }}" in workflow


def test_agent_workflows_are_read_only():
    dispatch = (ROOT / ".github/workflows/agent_dispatch.yml").read_text(encoding="utf-8-sig")
    issueops = (ROOT / ".github/workflows/agent_issue_ops.yml").read_text(encoding="utf-8-sig")
    for source in (dispatch, issueops):
        assert "contents: write" not in source
        assert "ANGEL_API_KEY" not in source
        assert "ALLOW_PRODUCTION_WRITES: '0'" in source
        assert "WRITER_ID: readonly_agent" in source
        assert "git push" not in source
    assert "run_cycle" not in dispatch
    assert "export_snapshots" not in dispatch
    assert "/run-cycle" not in issueops
    assert "/snapshots" not in issueops


def test_forensic_rows_validate_before_sort():
    source = (ROOT / "angel_prediction_engine.py").read_text(encoding="utf-8")
    validation = source.index("if len(r) == 18:")
    sort_call = source.index("valid_fl_rows.sort(")
    assert validation < sort_call


def test_news_dedup_collapses_whitespace():
    a = {"title": "Company   wins\torder", "source": "Feed A", "source_url": "https://a/x"}
    b = {"title": "Company wins order", "source": "Feed A", "source_url": "https://a/x"}
    assert news_dedup_key(a) == news_dedup_key(b)


def test_forward_validation_flags_can_run_together(monkeypatch):
    calls = []
    monkeypatch.setattr(fv, "freeze_target_a", lambda: calls.append("freeze"))
    monkeypatch.setattr(fv, "snapshot_target_b", lambda: calls.append("snapshot"))
    monkeypatch.setattr(sys, "argv", ["forward_validation.py", "--freeze-target-a", "--snapshot-target-b"])
    fv.main()
    assert calls == ["freeze", "snapshot"]


def test_linux_reports_contract_is_explicit():
    source = (ROOT / "scripts/forward_validation.py").read_text(encoding="utf-8")
    assert 'return Path("/mnt/c/AngelFNO_Workstation/reports")' in source


def test_direct_production_sink_calls_are_guarded(monkeypatch):
    from angel_prediction_engine import reconcile_next_day_gap_trades, sync_to_bigquery
    monkeypatch.delenv("ALLOW_PRODUCTION_WRITES", raising=False)
    monkeypatch.delenv("WRITER_ID", raising=False)
    with pytest.raises(RuntimeError, match="only market_bot"):
        reconcile_next_day_gap_trades(None, None, None, [], "2026-10-01 09:20:00", None)
    with pytest.raises(RuntimeError, match="only market_bot"):
        sync_to_bigquery([], [], {}, None)

"""Offline contract tests for free-tier LangSmith tracing."""

import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from observability.langsmith_free import (
    HARD_MONTHLY_CAP,
    PaidFeatureBlocked,
    agent_address,
    contains_secret,
    evaluate_free_tier,
    load_config,
    redact,
    refuse_paid,
    status_report,
    summarize_cycle,
    trace_prediction_cycle,
    uuid7,
)

ROOT = Path(__file__).resolve().parents[1]


def _environ(tmp_path, **overrides):
    base = {
        "LANGSMITH_TRACING": "true",
        "LANGSMITH_ENDPOINT": "https://api.smith.langchain.com",
        "LANGSMITH_API_KEY": "test-key",
        "LANGSMITH_AGENT_ID": "angel-fno",
        "LANGSMITH_AGENT_ENVIRONMENT": "local",
        "LANGSMITH_PROJECT": "angel-fno",
        "LANGSMITH_BUDGET_PATH": str(tmp_path / "budget.json"),
        "LANGSMITH_MIN_INTERVAL_SECONDS": "900",
        "LANGSMITH_MONTHLY_TRACE_CAP": "2000",
    }
    base.update(overrides)
    return base


def _cycle():
    return (
        [{
            "symbol": "RELIANCE",
            "rank": 1,
            "directional_bias": "CALL (CE) BULLISH",
            "ce_win_prob": 70.0,
            "pe_win_prob": 30.0,
            "intensity_score": 80,
            "expected_gap_pct": 0.4,
            "gap_direction": "GAP-UP (CE EXPLOSION)",
            "is_illiquid": False,
            "top_headline": "must not be traced",
        }],
        {"cycle": 3, "hit_rate_pct": 40.0, "recall_at_10": 0.4, "mean_rank": 12.0, "hits_count": 4, "misses_count": 6, "weights": {"news": 0.07}},
        {"top_ce_picks": [{"symbol": "RELIANCE"}], "top_pe_picks": []},
        "2026-10-23 09:20:00",
    )


def test_uuid7_is_rfc_variant():
    value = uuid7()
    assert value.version == 7
    assert value.variant == uuid.RFC_4122


def test_paid_features_have_no_override():
    with pytest.raises(PaidFeatureBlocked):
        refuse_paid("anthropic_or_other_llm")
    with pytest.raises(PaidFeatureBlocked):
        refuse_paid("extended_retention")
    os.environ["LANGSMITH_ALLOW_PAID"] = "1"
    try:
        with pytest.raises(PaidFeatureBlocked):
            refuse_paid("langsmith_deployment")
    finally:
        os.environ.pop("LANGSMITH_ALLOW_PAID", None)


def test_cap_cannot_exceed_free_buffer(tmp_path):
    config = load_config(_environ(tmp_path, LANGSMITH_MONTHLY_TRACE_CAP="999999"))
    assert config["monthly_cap"] == HARD_MONTHLY_CAP


def test_tracing_defaults_off_and_status_hides_key(tmp_path):
    environ = _environ(tmp_path, LANGSMITH_TRACING="false", LANGSMITH_API_KEY="lsv2_pt_secretvalue")
    report = status_report(environ)
    assert report["status"] == "disabled"
    assert report["key_present"] is True
    assert report["billing"] == "none"
    assert report["retention"] == "base_14d"
    blob = json.dumps(report)
    assert "lsv2_" not in blob
    assert "secretvalue" not in blob


def test_summary_drops_headline_and_limits_leaders():
    predictions = []
    for index in range(8):
        predictions.append({
            "symbol": "S%s" % index,
            "rank": index + 1,
            "directional_bias": "NEUTRAL",
            "top_headline": "secret headline",
            "source_url": "https://example.invalid/%s" % index,
        })
    summary = summarize_cycle(predictions, {}, {}, "2026-10-23 10:00:00")
    assert len(summary["outputs"]["top"]) == 5
    blob = json.dumps(summary)
    assert "headline" not in blob
    assert "example.invalid" not in blob
    assert summary["outputs"]["live_orders"] == 0
    assert evaluate_free_tier(summary)["score"] == 1.0


def test_redact_strips_secret_material():
    cleaned = redact({"note": "prefix lsv2_pt_abc123_def suffix", "api_key": "hidden", "nested": ["sk-ant-abc"]})
    assert cleaned["api_key"] == "[REDACTED]"
    assert "lsv2_" not in json.dumps(cleaned)
    assert "sk-ant-" not in json.dumps(cleaned)
    assert contains_secret({"note": "lsv2_pt_abc"}) is True


def test_missing_key_does_not_call_transport(tmp_path):
    calls = []

    def transport(request):
        calls.append(request)
        return {"status_code": 202, "text": ""}

    result = trace_prediction_cycle(*_cycle(), transport=transport, force=True, environ=_environ(tmp_path, LANGSMITH_API_KEY=""))
    assert result["status"] == "skipped_no_key"
    assert calls == []


def test_secret_payload_is_not_sent(tmp_path):
    calls = []

    def transport(request):
        calls.append(request)
        return {"status_code": 202, "text": ""}

    predictions, recon, picks, stamp = _cycle()
    predictions[0]["symbol"] = "lsv2_pt_should_not_send"
    result = trace_prediction_cycle(predictions, recon, picks, stamp, transport=transport, force=True, environ=_environ(tmp_path))
    assert result["status"] == "contract_failed"
    assert calls == []


def test_send_uses_agent_address_and_counts_budget(tmp_path):
    calls = []

    def transport(request):
        calls.append(request)
        return {"status_code": 202, "text": ""}

    result = trace_prediction_cycle(*_cycle(), transport=transport, force=True, environ=_environ(tmp_path))
    assert result["status"] == "sent"
    assert result["address_used"] is True
    assert calls[0]["payload"]["address"] == "lrn:agents/angel-fno/environments/local"
    assert "session_name" not in calls[0]["payload"]
    assert calls[0]["payload"]["run_type"] == "chain"
    assert calls[0]["url"].endswith("/api/v1/runs")
    assert result["traces_sent_this_month"] == 1
    feedback_urls = [call["url"] for call in calls[1:]]
    assert feedback_urls == [
        "https://api.smith.langchain.com/api/v1/feedback",
        "https://api.smith.langchain.com/api/v1/feedback",
    ]
    stored = json.loads((tmp_path / "budget.json").read_text(encoding="utf-8"))
    assert stored["traces_sent"] == 1


def test_agent_address_forbidden_falls_back_once(tmp_path):
    calls = []

    def transport(request):
        calls.append(request)
        if request["url"].endswith("/runs") and "address" in request["payload"]:
            return {"status_code": 403, "text": "agent addressing disabled"}
        return {"status_code": 202, "text": ""}

    result = trace_prediction_cycle(*_cycle(), transport=transport, force=True, environ=_environ(tmp_path))
    assert result["status"] == "sent"
    assert result["address_used"] is False
    assert calls[1]["payload"]["session_name"] == "angel-fno"
    assert "address" not in calls[1]["payload"]


def test_rejected_trace_does_not_spend_budget(tmp_path):
    def transport(request):
        return {"status_code": 500, "text": "upstream"}

    result = trace_prediction_cycle(*_cycle(), transport=transport, force=True, environ=_environ(tmp_path))
    assert result["status"] == "rejected"
    assert result["traces_sent_this_month"] == 0
    assert not (tmp_path / "budget.json").exists()


def test_interval_and_cap(tmp_path):
    calls = []

    def transport(request):
        calls.append(request["url"])
        return {"status_code": 202, "text": ""}

    environ = _environ(tmp_path, LANGSMITH_MIN_INTERVAL_SECONDS="900", LANGSMITH_MONTHLY_TRACE_CAP="1")
    now = datetime(2026, 10, 23, 4, 0, tzinfo=timezone.utc)
    first = trace_prediction_cycle(*_cycle(), transport=transport, now=now, environ=environ)
    second = trace_prediction_cycle(*_cycle(), transport=transport, now=now, environ=environ)
    assert first["status"] == "sent"
    assert second["status"] == "budget_exhausted"
    run_posts = [url for url in calls if url.endswith("/runs")]
    assert len(run_posts) == 1


def test_sample_out_does_not_post(tmp_path):
    calls = []

    def transport(request):
        calls.append(request)
        return {"status_code": 202, "text": ""}

    environ = _environ(tmp_path, LANGSMITH_MIN_INTERVAL_SECONDS="900", LANGSMITH_MONTHLY_TRACE_CAP="10")
    now = datetime(2026, 10, 23, 4, 0, tzinfo=timezone.utc)
    trace_prediction_cycle(*_cycle(), transport=transport, now=now, environ=environ)
    later = datetime(2026, 10, 23, 4, 5, tzinfo=timezone.utc)
    sampled = trace_prediction_cycle(*_cycle(), transport=transport, now=later, environ=environ)
    assert sampled["status"] == "sampled_out"
    assert sum(1 for call in calls if call["url"].endswith("/runs")) == 1


def test_engine_hook_swallows_tracer_failure(monkeypatch):
    import angel_prediction_engine as engine

    def boom(*args, **kwargs):
        raise RuntimeError("langsmith down")

    monkeypatch.setattr("observability.langsmith_free.trace_prediction_cycle", boom)
    engine._emit_free_langsmith_trace([], {}, {}, "2026-10-23 09:20:00")


def test_cli_status_is_one_cp1252_json_document(tmp_path):
    env = os.environ.copy()
    env.update(_environ(tmp_path, LANGSMITH_TRACING="false", LANGSMITH_API_KEY=""))
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-m", "observability.langsmith_free", "--status", "--json-only"],
        cwd=str(ROOT),
        capture_output=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0
    stdout = proc.stdout.decode("utf-8")
    proc.stdout.decode("cp1252")
    document = json.loads(stdout)
    assert document["status"] == "disabled"
    assert document["billing"] == "none"
    assert stdout.count("\n") == 1


def test_source_has_no_live_secret_and_blocks_deepagents():
    source = (ROOT / "observability" / "langsmith_free.py").read_text(encoding="utf-8")
    assert "lsv2_pt_" not in source
    assert "create_deep_agent" not in source
    assert "ANTHROPIC_API_KEY" in source
    engine = (ROOT / "angel_prediction_engine.py").read_text(encoding="utf-8")
    assert "_emit_free_langsmith_trace" in engine
    assert agent_address({"agent_id": "angel-fno", "environment": "local"}) == "lrn:agents/angel-fno/environments/local"

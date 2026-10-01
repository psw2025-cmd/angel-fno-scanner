import json

import angel_prediction_engine as ape


def test_bq_project_prefers_explicit_environment(monkeypatch, tmp_path):
    key = tmp_path / "sa.json"
    key.write_text(json.dumps({"type": "service_account", "project_id": "fallback-project"}), encoding="utf-8")
    monkeypatch.setattr(ape, "KEY_PATH", str(key))
    monkeypatch.setenv("BQ_PROJECT_ID", "explicit-project")
    assert ape.resolve_bq_project_id() == "explicit-project"


def test_bq_project_falls_back_to_service_account(monkeypatch, tmp_path):
    key = tmp_path / "sa.json"
    key.write_text(json.dumps({"type": "service_account", "project_id": "fallback-project"}), encoding="utf-8")
    monkeypatch.setattr(ape, "KEY_PATH", str(key))
    monkeypatch.delenv("BQ_PROJECT_ID", raising=False)
    monkeypatch.delenv("SHEETS_KEY_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    assert ape.resolve_bq_project_id() == "fallback-project"


def test_bq_project_fails_closed_when_both_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(ape, "KEY_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setattr("credentials.DEFAULT_KEY_PATHS", [])
    monkeypatch.delenv("BQ_PROJECT_ID", raising=False)
    monkeypatch.delenv("SHEETS_KEY_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    assert ape.resolve_bq_project_id() == ""
    try:
        ape.get_bigquery_client()
    except RuntimeError as exc:
        assert "billing guardrail" in str(exc)
    else:
        raise AssertionError("BigQuery access must fail closed without a project id")

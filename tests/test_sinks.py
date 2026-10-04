import importlib

from angel_prediction_engine import deduplicate_news_rows, normalize_sheet_rows


def test_sheet_rows_are_rectangular_and_fixed_width():
    rows = [["a", "b"], ["c"], ["d", "e", "f"]]
    normalized = normalize_sheet_rows(rows, 3)
    assert normalized == [["a", "b", ""], ["c", "", ""], ["d", "e", "f"]]
    assert len({len(row) for row in normalized}) == 1


def test_bigquery_news_replay_dedup_preserves_cross_source_rows():
    rows = [
        {"symbol": "TEST", "source": "Feed A", "source_url": "https://a.example/1", "title": "Same headline"},
        {"symbol": "TEST", "source": "Feed A", "source_url": "https://a.example/1", "title": "Same headline"},
        {"symbol": "TEST", "source": "Feed B", "source_url": "https://b.example/1", "title": "Same headline"},
    ]
    result = deduplicate_news_rows(rows)
    assert len(result) == 2
    assert {row["source"] for row in result} == {"Feed A", "Feed B"}


def test_scanner_import_does_not_require_sheet_credentials_at_module_import(monkeypatch, tmp_path):
    monkeypatch.delenv("SHEET_ID", raising=False)
    monkeypatch.delenv("SHEETS_KEY_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setattr("credentials.REPO_ROOT", tmp_path)
    scanner = importlib.import_module("scanner")
    importlib.reload(scanner)
    assert scanner.SHEET_ID == ""


def test_bigquery_news_append_uses_existing_table_schema():
    source = importlib.import_module("angel_prediction_engine")

    class Table:
        schema = ["run_id:STRING", "symbol:STRING"]

    config = source.build_news_append_job_config(Table())
    assert config.autodetect is False
    assert config.schema == Table.schema
    assert config.write_disposition == source.bigquery.WriteDisposition.WRITE_APPEND

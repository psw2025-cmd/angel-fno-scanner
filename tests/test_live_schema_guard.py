"""An incomplete schema must not be allowed to replace option_predictions_live."""
from __future__ import annotations

import copy

import pytest

from tools.live_schema_guard import SchemaGuardError, assert_truncate_schema_safe
from tools.schema_validator import load_schema


def _live_from(committed):
    return [{"name": field["name"], "type": field["type"]} for field in committed]


def test_committed_schema_declares_string_run_id_and_provenance():
    committed = load_schema("option_predictions_live")
    by_name = {field["name"]: field["type"] for field in committed}
    assert by_name["run_id"] == "STRING"
    assert by_name["git_sha"] == "STRING"
    assert by_name["writer_id"] == "STRING"
    assert by_name["source_timestamp"] == "TIMESTAMP"
    assert by_name["cycle_id"] == "STRING"
    assert_truncate_schema_safe(committed, _live_from(committed), autodetect=False)


def test_committed_schema_without_provenance_fails_closed():
    committed = load_schema("option_predictions_live")
    narrow = [field for field in committed if field["name"] != "run_id"]
    with pytest.raises(SchemaGuardError, match="missing=\\['run_id'\\]"):
        assert_truncate_schema_safe(narrow, _live_from(committed))


def test_integer_run_id_in_committed_schema_is_refused():
    committed = copy.deepcopy(load_schema("option_predictions_live"))
    for field in committed:
        if field["name"] == "run_id":
            field["type"] = "INTEGER"
    with pytest.raises(SchemaGuardError, match="run_id=INT64 expected STRING"):
        assert_truncate_schema_safe(committed, _live_from(committed))


def test_live_table_missing_provenance_refuses_truncate():
    committed = load_schema("option_predictions_live")
    live = [field for field in _live_from(committed) if field["name"] not in {
        "run_id", "git_sha", "writer_id", "source_timestamp", "cycle_id",
    }]
    with pytest.raises(SchemaGuardError, match="missing run_id"):
        assert_truncate_schema_safe(committed, live)


def test_narrower_load_cannot_replace_a_complete_live_table():
    committed = load_schema("option_predictions_live")
    live = _live_from(committed)
    stale = [field for field in committed if field["name"] not in {
        "run_id", "git_sha", "writer_id", "source_timestamp", "cycle_id",
    }]
    with pytest.raises(SchemaGuardError, match="missing=\\["):
        assert_truncate_schema_safe(stale, live, load_fields=stale)


def test_autodetect_truncate_is_refused():
    committed = load_schema("option_predictions_live")
    with pytest.raises(SchemaGuardError, match="autodetect WRITE_TRUNCATE is refused"):
        assert_truncate_schema_safe(committed, _live_from(committed), autodetect=True)


def test_stale_writer_cannot_drop_a_live_column():
    committed = load_schema("option_predictions_live")
    live = _live_from(committed)
    load = [field for field in committed if field["name"] != "snapshot_timestamp"]
    with pytest.raises(SchemaGuardError, match="narrower than the live table"):
        assert_truncate_schema_safe(committed, live, load_fields=load)

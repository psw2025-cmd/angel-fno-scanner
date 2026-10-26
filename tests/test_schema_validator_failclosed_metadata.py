"""Offline fail-closed regressions for unsupported or ambiguous BigQuery schemas.

These tests use temporary schema files only; no BigQuery credentials or network.
"""
import json

import pytest

from tools import schema_validator as validator


@pytest.mark.parametrize("type_name,value", [
    ("BIGNUMERIC", 1.25),
    ("STRUCT", {"x": 1}),
    ("NOT_A_TYPE", "arbitrary"),
])
def test_unsupported_bigquery_type_is_not_silently_accepted(type_name, value):
    error = validator._check_type(value, type_name, "unknown_column")
    assert error is not None
    assert "unknown_column" in error
    assert type_name in error


def test_empty_schema_is_rejected_before_validating_rows(tmp_path, monkeypatch):
    (tmp_path / "test_table.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(validator, "SCHEMAS_DIR", tmp_path)
    monkeypatch.setattr(validator, "_SCHEMA_CACHE", {})
    with pytest.raises(ValueError, match="empty"):
        validator.validate_rows("test_table", [{"arbitrary": "value"}])


def test_duplicate_schema_column_is_rejected_before_validating_rows(tmp_path, monkeypatch):
    fields = [
        {"name": "symbol", "type": "STRING", "mode": "REQUIRED"},
        {"name": "symbol", "type": "INT64", "mode": "NULLABLE"},
    ]
    (tmp_path / "test_table.json").write_text(json.dumps(fields), encoding="utf-8")
    monkeypatch.setattr(validator, "SCHEMAS_DIR", tmp_path)
    monkeypatch.setattr(validator, "_SCHEMA_CACHE", {})
    with pytest.raises(ValueError, match="duplicate"):
        validator.validate_rows("test_table", [{"symbol": "NIFTY"}])


@pytest.mark.parametrize("field", [
    {"name": "value", "type": "BIGNUMERIC", "mode": "NULLABLE"},
    {"name": "value", "mode": "NULLABLE"},
    {"name": "value", "type": "STRING", "mode": "REPEATED"},
    {"name": "value", "type": "STRING", "mode": "UNKNOWN"},
])
def test_invalid_field_metadata_rejected_even_when_value_is_null(
    tmp_path, monkeypatch, field
):
    (tmp_path / "test_table.json").write_text(json.dumps([field]), encoding="utf-8")
    monkeypatch.setattr(validator, "SCHEMAS_DIR", tmp_path)
    monkeypatch.setattr(validator, "_SCHEMA_CACHE", {})
    with pytest.raises(ValueError, match="unsupported|missing"):
        validator.validate_rows("test_table", [{"value": None}])

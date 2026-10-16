"""CDX-02 regression: float->INT64 coercion and FLOAT/INTEGER canonicalisation (PR #97)."""
import pytest

from tools.live_schema_guard import (
    SchemaGuardError,
    assert_truncate_schema_safe,
    sanitize_bq_row,
)
from tools.schema_validator import load_schema, validate_rows


def test_float_counter_in_news_row_becomes_int():
    row = sanitize_bq_row("market_news_sentiment", {"source_count": 3.0, "severity_level": 2.0, "title": "x"})
    assert row["source_count"] == 3 and type(row["source_count"]) is int
    assert row["severity_level"] == 2 and type(row["severity_level"]) is int
    assert row["title"] == "x"


def test_float_cycle_number_in_calibration_row_becomes_int():
    row = sanitize_bq_row("prediction_calibration_log", {"cycle_number": 4.0})
    assert row["cycle_number"] == 4 and type(row["cycle_number"]) is int


def test_input_row_not_mutated_and_float_columns_untouched():
    src = {"source_count": 3.0, "tone_score": 0.25}
    out = sanitize_bq_row("market_news_sentiment", src)
    assert src["source_count"] == 3.0 and type(src["source_count"]) is float
    assert out["tone_score"] == 0.25 and type(out["tone_score"]) is float


def test_none_bool_and_int_left_alone():
    out = sanitize_bq_row("market_news_sentiment", {"source_count": None, "severity_level": 5})
    assert out == {"source_count": None, "severity_level": 5}
    flagged = sanitize_bq_row("market_news_sentiment", {"source_count": True})
    assert flagged["source_count"] is True  # validator, not the sanitizer, rejects bool


@pytest.mark.parametrize("bad", ["abc", float("nan"), float("inf"), object()])
def test_unconvertible_value_fails_closed_not_zero(bad):
    with pytest.raises(SchemaGuardError):
        sanitize_bq_row("market_news_sentiment", {"source_count": bad})


def test_sanitized_news_row_passes_schema_validator():
    row = {f["name"]: None for f in load_schema("market_news_sentiment")}
    row.update({"source_count": 7.0, "severity_level": 1.0})
    validate_rows("market_news_sentiment", [sanitize_bq_row("market_news_sentiment", row)])


def _committed():
    return load_schema("option_predictions_live")


def _live_with_legacy_names():
    legacy = {"FLOAT64": "FLOAT", "INT64": "INTEGER"}
    return [{**f, "type": legacy.get(f["type"].upper(), f["type"])} for f in _committed()]


def test_legacy_float_integer_names_do_not_count_as_retype():
    assert_truncate_schema_safe(_committed(), _live_with_legacy_names(), load_fields=_committed())


def test_real_retype_is_still_refused():
    live = [dict(f) for f in _committed()]
    target = next(f for f in live if f["type"].upper() == "FLOAT64")
    target["type"] = "STRING"
    with pytest.raises(SchemaGuardError, match="retype"):
        assert_truncate_schema_safe(_committed(), live, load_fields=_committed())

"""
tests/test_schema_validator.py

Unit tests for tools/schema_validator.py.
Verifies fail-fast schema validation against schemas/*.json.
"""

from __future__ import annotations

import datetime
from pathlib import Path
import pytest

from tools.schema_validator import (
    SchemaValidationError,
    load_schema,
    validate_row,
    validate_rows,
)

ALL_TABLES = [
    "option_predictions_live",
    "market_news_sentiment",
    "next_day_gap_predictions",
    "prediction_calibration_log",
    "cycle_status",
]


# ---------------------------------------------------------------------------
# 1. Schema Loading Tests
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("table_name", ALL_TABLES)
def test_all_registered_schemas_load_cleanly(table_name: str) -> None:
    schema = load_schema(table_name)
    assert isinstance(schema, list)
    assert len(schema) > 0
    for field in schema:
        assert "name" in field
        assert "type" in field
        assert "mode" in field
        assert field["mode"] in ("NULLABLE", "REQUIRED", "REPEATED")


def test_load_schema_raises_on_nonexistent_table() -> None:
    with pytest.raises(FileNotFoundError, match="Declarative schema definition not found"):
        load_schema("non_existent_table_xyz")


# ---------------------------------------------------------------------------
# 2. Valid Rows Tests for All 5 Tables
# ---------------------------------------------------------------------------
def test_valid_row_option_predictions_live() -> None:
    row = {
        "symbol": "NIFTY",
        "rank": 1,
        "directional_bias": "CALL",
        "spot_ltp": 25000.5,
        "expiry": "2026-10-29",
        "confidence_pct": 85.5,
        "ce_win_prob": 0.75,
        "pe_win_prob": 0.25,
        "action_rating": "STRONG_BUY",
        "intensity_score": 90,
        "atm_pcr": 1.15,
        "max_pain": 25000.0,
        "ce_ltp": 150.0,
        "ce_chg_pct": 25.5,
        "ce_oi": 1500000,
        "ce_oi_change_pct": 12.0,
        "ce_iv": 14.5,
        "ce_delta": 0.52,
        "ce_gamma": 0.001,
        "ce_theta": -12.5,
        "ce_vega": 25.0,
        "ce_bid_ask_spread": 0.05,
        "pe_ltp": 80.0,
        "pe_chg_pct": -15.0,
        "pe_oi": 1800000,
        "pe_oi_change_pct": -5.0,
        "pe_iv": 15.0,
        "pe_delta": -0.48,
        "pe_gamma": 0.001,
        "pe_theta": -11.0,
        "pe_vega": 24.0,
        "pe_bid_ask_spread": 0.06,
        "news_sentiment_score": 0.65,
        "news_impact_rating": "HIGH",
        "top_news_headline": "Index rallies strongly",
        "news_source_tier": "TIER_1",
        "news_severity_level": 2,
        "positive_prob": 0.70,
        "negative_prob": 0.15,
        "already_priced_in_prob": 0.15,
        "market_confirmation": "CONFIRMED",
        "expected_gap_pct": 0.45,
        "gap_direction": "GAP_UP",
        "pre_open_conviction_pct": 82.0,
        "target_open_strike": "25100CE",
        "expected_move_band": "24950-25150",
        "data_freshness_status": "FRESH",
        "snapshot_timestamp": "2026-10-05T09:15:00+05:30",
        "source_timestamp": datetime.datetime(2026, 10, 5, 9, 15, 0, tzinfo=datetime.timezone.utc),
        "cycle_id": "cycle_20261005_091500",
        "run_id": "37261595211",
        "git_sha": "d425b4507e8cb3c2edd216e244d9d5305b454042",
        "writer_id": "market_bot",
    }
    validate_rows("option_predictions_live", [row])


def test_valid_row_market_news_sentiment() -> None:
    row = {
        "symbol": "RELIANCE",
        "title": "Strong Q2 Earnings Beat Estimates",
        "source_count": 3,
        "source_agreement_pct": 95.0,
        "impact_rating": "HIGH",
        "tone_score": 0.85,
        "sentiment": "Positive",
        "source": "Moneycontrol",
        "news_type": "Corporate",
        "filing_type": "Q2_RESULTS",
        "timestamp": "2026-10-05 09:15:00",
        "severity_level": 3,
        "source_tier": "TIER_1",
        "positive_prob": 0.90,
        "negative_prob": 0.05,
        "already_priced_in_prob": 0.05,
        "market_confirmation": "CONFIRMED",
        "expected_move_band": "+1.5% to +2.5%",
        "source_url": "https://example.com/article1",
        "canonical_url": "https://example.com/article1",
        "verified_catalyst": True,
        "run_id": "37261595211",
        "git_sha": "d425b45",
        "writer_id": "market_bot",
        "source_timestamp": "2026-10-05 09:15:00",
        "cycle_id": "cycle_20261005_091500",
    }
    validate_rows("market_news_sentiment", [row])


def test_valid_row_next_day_gap_predictions() -> None:
    row = {
        "prediction_date": "2026-10-05",
        "predicted_at_ist": "15:20:00",
        "symbol": "TCS",
        "target_date": datetime.date(2026, 10, 6),
        "side": "GAP_UP",
        "spot_ltp": 4250.0,
        "target_strike": "4300CE",
        "contract_symbol": "TCS26OCT4300CE",
        "entry_ltp": 45.0,
        "expected_gap_pct": 1.5,
        "conviction_pct": 82.0,
        "stop_loss_ltp": 30.0,
        "target_ltp": 70.0,
        "rationale": "Strong pre-close breakout with high volume",
        "news_catalyst": "New multibillion cloud deal",
        "dollar_gamma": 150000.0,
        "actual_open_ltp": None,
        "actual_return_pct": None,
        "outcome": "PENDING_OPEN",
        "reconciled_at_ist": None,
        "run_id": "37261595211",
        "git_sha": "d425b45",
        "writer_id": "market_bot",
        "source_timestamp": "2026-10-05 15:20:00",
        "cycle_id": "cycle_20261005_152000",
    }
    validate_rows("next_day_gap_predictions", [row])


def test_valid_row_prediction_calibration_log() -> None:
    row = {
        "timestamp": "2026-10-05T15:35:00Z",
        "cycle_number": 14,
        "top10_hit_rate_pct": 80.0,
        "recall_at_10": 0.8,
        "mean_rank_of_top10": 2.4,
        "predicted_top10": '["NIFTY26OCT25000CE", "RELIANCE26OCT3100CE"]',
        "actual_top10": '["NIFTY26OCT25000CE", "RELIANCE26OCT3100CE"]',
        "hits": '["NIFTY26OCT25000CE"]',
        "misses": '["SBIN26OCT800CE"]',
        "miss_root_causes": '{"SBIN26OCT800CE": "late sector rotation"}',
        "updated_weights_json": '{"momentum": 0.4, "news": 0.3, "oi": 0.3}',
        "run_id": "37261595211",
        "git_sha": "d425b45",
        "writer_id": "market_bot",
        "source_timestamp": "2026-10-05 15:35:00",
        "cycle_id": "cycle_20261005_153500",
    }
    validate_rows("prediction_calibration_log", [row])


def test_valid_row_cycle_status() -> None:
    row = {
        "cycle_id": "cycle_20261005_091500",
        "run_id": "37261595211",
        "git_sha": "d425b4507e8cb3c2edd216e244d9d5305b454042",
        "sink": "option_predictions_live",
        "status": "COMPLETED",
        "records_count": 219,
        "error_message": None,
        "created_at": "2026-10-05T09:15:30+05:30",
    }
    validate_rows("cycle_status", [row])


def test_empty_rows_batch_passes() -> None:
    validate_rows("option_predictions_live", [])


# ---------------------------------------------------------------------------
# 3. Fail-Fast Rejection of Unknown / Extra Columns (D-09 Prevention)
# ---------------------------------------------------------------------------
def test_rejects_unknown_extra_column() -> None:
    row = {
        "symbol": "NIFTY",
        "rank": 1,
        "totally_bogus_column_name": "should_fail_immediately",
    }
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_rows("option_predictions_live", [row])

    err = exc_info.value
    assert err.table_name == "option_predictions_live"
    assert err.row_index == 0
    assert any("Undeclared column 'totally_bogus_column_name'" in e for e in err.errors)


def test_rejects_non_dict_row() -> None:
    with pytest.raises(SchemaValidationError, match="Expected dictionary"):
        validate_rows("cycle_status", ["not_a_dict"])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# 4. REQUIRED Column Enforcement
# ---------------------------------------------------------------------------
def test_rejects_missing_required_column_in_cycle_status() -> None:
    # Missing required field 'status'
    row = {
        "cycle_id": "c1",
        "run_id": "r1",
        "git_sha": "g1",
        "sink": "s1",
        # "status" is omitted!
        "created_at": "2026-10-05T09:15:00Z",
    }
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_rows("cycle_status", [row])
    assert any("Missing REQUIRED column 'status'" in e for e in exc_info.value.errors)


def test_rejects_none_value_for_required_column() -> None:
    # 'status' is REQUIRED but provided as None
    row = {
        "cycle_id": "c1",
        "run_id": "r1",
        "git_sha": "g1",
        "sink": "s1",
        "status": None,
        "created_at": "2026-10-05T09:15:00Z",
    }
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_rows("cycle_status", [row])
    assert any("Column 'status' is REQUIRED but value is None" in e for e in exc_info.value.errors)


# ---------------------------------------------------------------------------
# 5. Strict Type Validation Tests
# ---------------------------------------------------------------------------
def test_rejects_int_for_string_field() -> None:
    # run_id is STRING, integer 37261595211 must be rejected
    row = {
        "cycle_id": "c1",
        "run_id": 37261595211,  # int instead of str
        "git_sha": "g1",
        "sink": "s1",
        "status": "COMPLETED",
        "created_at": "2026-10-05T09:15:00Z",
    }
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_rows("cycle_status", [row])
    assert any("Field 'run_id' expects STRING, got int" in e for e in exc_info.value.errors)


def test_rejects_bool_for_int64_field() -> None:
    # In Python, isinstance(True, int) is True! Ensure bool is rejected for INT64.
    row = {
        "cycle_id": "c1",
        "run_id": "r1",
        "git_sha": "g1",
        "sink": "s1",
        "status": "COMPLETED",
        "records_count": True,  # bool instead of int
        "created_at": "2026-10-05T09:15:00Z",
    }
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_rows("cycle_status", [row])
    assert any("Field 'records_count' expects INT64, got bool" in e for e in exc_info.value.errors)


def test_rejects_bool_for_float64_field() -> None:
    # Ensure bool is rejected for FLOAT64.
    row = {
        "symbol": "NIFTY",
        "spot_ltp": True,  # bool instead of float
    }
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_rows("option_predictions_live", [row])
    assert any("Field 'spot_ltp' expects FLOAT64, got bool" in e for e in exc_info.value.errors)


def test_rejects_nan_and_inf_for_float64_field() -> None:
    row_nan = {"symbol": "NIFTY", "spot_ltp": float("nan")}
    with pytest.raises(SchemaValidationError) as exc_nan:
        validate_rows("option_predictions_live", [row_nan])
    assert any("finite FLOAT64" in e for e in exc_nan.value.errors)

    row_inf = {"symbol": "NIFTY", "spot_ltp": float("inf")}
    with pytest.raises(SchemaValidationError) as exc_inf:
        validate_rows("option_predictions_live", [row_inf])
    assert any("finite FLOAT64" in e for e in exc_inf.value.errors)


def test_rejects_datetime_for_date_field() -> None:
    # BigQuery DATE expects datetime.date or 'YYYY-MM-DD' str, not datetime.datetime!
    row = {
        "prediction_date": datetime.datetime(2026, 10, 5, 12, 0, 0),  # datetime instead of date
        "predicted_at_ist": "15:20:00",
        "symbol": "TCS",
        "target_date": "2026-10-06",
        "side": "GAP_UP",
        "spot_ltp": 4250.0,
        "target_strike": "4300CE",
        "contract_symbol": "TCS26OCT4300CE",
        "entry_ltp": 45.0,
        "expected_gap_pct": 1.5,
        "conviction_pct": 82.0,
        "stop_loss_ltp": 30.0,
        "target_ltp": 70.0,
        "rationale": "Breakout",
    }
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_rows("next_day_gap_predictions", [row])
    assert any("Field 'prediction_date' expects DATE" in e for e in exc_info.value.errors)


def test_rejects_invalid_date_format_string() -> None:
    row = {
        "prediction_date": "05/10/2026",  # wrong format (not YYYY-MM-DD)
        "predicted_at_ist": "15:20:00",
        "symbol": "TCS",
        "target_date": "2026-10-06",
        "side": "GAP_UP",
        "spot_ltp": 4250.0,
        "target_strike": "4300CE",
        "contract_symbol": "TCS26OCT4300CE",
        "entry_ltp": 45.0,
        "expected_gap_pct": 1.5,
        "conviction_pct": 82.0,
        "stop_loss_ltp": 30.0,
        "target_ltp": 70.0,
        "rationale": "Breakout",
    }
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_rows("next_day_gap_predictions", [row])
    assert any("expects DATE" in e for e in exc_info.value.errors)


def test_rejects_invalid_timestamp_string() -> None:
    row = {
        "cycle_id": "c1",
        "run_id": "r1",
        "git_sha": "g1",
        "sink": "s1",
        "status": "COMPLETED",
        "created_at": "not-a-valid-timestamp-string",
    }
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_rows("cycle_status", [row])
    assert any("expects TIMESTAMP" in e for e in exc_info.value.errors)

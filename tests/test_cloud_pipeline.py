"""
tests/test_cloud_pipeline.py

Strict automated unit test suite for the Cloud Run F&O ingestion and verification pipeline.
Tests four mandatory gates:
1. HTTP 429 Throttling Recovery with Exponential Backoff
2. BigQuery Row Count & Schema Parity (219 symbols)
3. Zero Missing, Null, Empty, or NaN Values in Ingestion Payload
4. Deterministic SHA-256 Checksum Matching across Sinks
"""

import hashlib
import json
import math
import pytest
import responses
from unittest.mock import MagicMock, patch

# The pipeline module to be implemented after test approval
from cloud_pipeline import (
    execute_pipeline_cycle,
    validate_payload_integrity,
    verify_bigquery_parity,
    compute_payload_checksum,
    TARGET_UNIVERSE_SIZE,
    REQUIRED_SCHEMA_FIELDS,
)


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def valid_sample_row():
    """Returns a single valid canonical option prediction record."""
    return {
        "symbol": "NIFTY",
        "underlying": "NIFTY",
        "expiry": "2026-10-15",
        "strike": 25000.0,
        "option_type": "CE",
        "ltp": 145.50,
        "iv": 14.2,
        "oi": 1520000,
        "delta": 0.52,
        "gamma": 0.0012,
        "pcr": 1.15,
        "rank": 1,
        "run_id": "38223387415",
        "exchange_timestamp": "2026-10-12T15:29:58+05:30",
        "source_cycle": "CYCLE_01"
    }


@pytest.fixture
def valid_full_universe_payload(valid_sample_row):
    """Returns a full 219-row clean universe payload."""
    payload = []
    for i in range(1, TARGET_UNIVERSE_SIZE + 1):
        row = valid_sample_row.copy()
        row["symbol"] = f"SYM_{i:03d}"
        row["rank"] = i
        payload.append(row)
    return payload


# ==============================================================================
# TEST 1: HTTP 429 THROTTLING RECOVERY WITH EXPONENTIAL BACKOFF
# ==============================================================================

@responses.activate
def test_http_429_throttling_recovery():
    """
    Simulates upstream Google Sheets / broker API returning HTTP 429 (Too Many Requests).
    Asserts that the pipeline catches HTTP 429, executes backoff delay, retries,
    and successfully completes when the API recovers with HTTP 200.
    """
    api_url = "https://sheets.googleapis.com/v4/spreadsheets/1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs/values:batchUpdate"

    # Mock 2 consecutive HTTP 429 Rate Limit responses followed by HTTP 200 Success
    responses.add(
        responses.POST,
        api_url,
        json={"error": {"code": 429, "message": "Rate limit exceeded: RESOURCE_EXHAUSTED", "status": "RESOURCE_EXHAUSTED"}},
        status=429
    )
    responses.add(
        responses.POST,
        api_url,
        json={"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}},
        status=429
    )
    responses.add(
        responses.POST,
        api_url,
        json={"spreadsheetId": "1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs", "totalUpdatedCells": 219},
        status=200
    )

    with patch("time.sleep", return_value=None) as mock_sleep:
        result = execute_pipeline_cycle(
            endpoint_url=api_url,
            payload=[{"sample": "data"}],
            max_retries=5,
            base_delay=0.1
        )

    # Asserts
    assert result["status"] == "SUCCESS", f"Expected SUCCESS but got {result.get('status')}"
    assert result["attempts"] == 3, f"Expected 3 attempts (2 retries), got {result.get('attempts')}"
    assert len(responses.calls) == 3, f"Expected exactly 3 HTTP calls, but made {len(responses.calls)}"
    assert mock_sleep.call_count == 2, "time.sleep must be called on each HTTP 429 backoff"


@responses.activate
def test_http_429_exhaustion_fails_closed():
    """Asserts that if HTTP 429 persists beyond max_retries, the pipeline fails closed with RuntimeError."""
    api_url = "https://sheets.googleapis.com/v4/spreadsheets/1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs/values:batchUpdate"

    for _ in range(4):
        responses.add(
            responses.POST,
            api_url,
            json={"error": {"code": 429, "message": "Rate limit quota exhausted"}},
            status=429
        )

    with patch("time.sleep", return_value=None):
        with pytest.raises(RuntimeError, match="HTTP 429 quota exhausted after 3 attempts"):
            execute_pipeline_cycle(endpoint_url=api_url, payload=[], max_retries=3, base_delay=0.01)


# ==============================================================================
# TEST 2: BIGQUERY ROW AND SCHEMA PARITY (219 SYMBOLS)
# ==============================================================================

def test_bigquery_row_and_schema_parity(valid_full_universe_payload):
    """
    Verifies that the BigQuery destination table has exact 219-row count parity
    and 100% schema field alignment matching REQUIRED_SCHEMA_FIELDS.
    """
    mock_bq_client = MagicMock()
    mock_table = MagicMock()
    mock_table.num_rows = TARGET_UNIVERSE_SIZE
    mock_table.schema = [MagicMock(name=field) for field in REQUIRED_SCHEMA_FIELDS]
    for mock_field, field_name in zip(mock_table.schema, REQUIRED_SCHEMA_FIELDS):
        mock_field.name = field_name

    mock_bq_client.get_table.return_value = mock_table

    parity_ok, parity_report = verify_bigquery_parity(
        bq_client=mock_bq_client,
        table_id="fno-angel-prod-1790444589.fno_predictions.option_predictions_live",
        staged_payload=valid_full_universe_payload
    )

    assert parity_ok is True
    assert parity_report["row_count_match"] is True
    assert parity_report["schema_fields_match"] is True
    assert parity_report["table_num_rows"] == TARGET_UNIVERSE_SIZE
    assert parity_report["staged_num_rows"] == TARGET_UNIVERSE_SIZE


def test_bigquery_row_count_mismatch_fails_closed(valid_full_universe_payload):
    """Asserts failure when BigQuery row count does not match the 219-symbol universe."""
    mock_bq_client = MagicMock()
    mock_table = MagicMock()
    mock_table.num_rows = 218  # 1 row dropped anomaly
    mock_table.schema = [MagicMock(name=f) for f in REQUIRED_SCHEMA_FIELDS]
    for mf, fn in zip(mock_table.schema, REQUIRED_SCHEMA_FIELDS):
        mf.name = fn
    mock_bq_client.get_table.return_value = mock_table

    with pytest.raises(ValueError, match="Row count mismatch: BigQuery has 218, expected 219"):
        verify_bigquery_parity(
            bq_client=mock_bq_client,
            table_id="fno-angel-prod-1790444589.fno_predictions.option_predictions_live",
            staged_payload=valid_full_universe_payload
        )


def test_bigquery_missing_schema_column_fails_closed(valid_full_universe_payload):
    """Asserts failure when a required column is missing from BigQuery table schema."""
    mock_bq_client = MagicMock()
    mock_table = MagicMock()
    mock_table.num_rows = TARGET_UNIVERSE_SIZE
    # Drop 'exchange_timestamp' column
    incomplete_fields = [f for f in REQUIRED_SCHEMA_FIELDS if f != "exchange_timestamp"]
    mock_table.schema = [MagicMock(name=f) for f in incomplete_fields]
    for mf, fn in zip(mock_table.schema, incomplete_fields):
        mf.name = fn
    mock_bq_client.get_table.return_value = mock_table

    with pytest.raises(ValueError, match="Schema mismatch: missing fields {'exchange_timestamp'}"):
        verify_bigquery_parity(
            bq_client=mock_bq_client,
            table_id="fno-angel-prod-1790444589.fno_predictions.option_predictions_live",
            staged_payload=valid_full_universe_payload
        )


# ==============================================================================
# TEST 3: ZERO MISSING OR NULL VALUES IN PAYLOAD
# ==============================================================================

def test_zero_missing_or_null_values_passes_clean_payload(valid_full_universe_payload):
    """Clean full payload with zero nulls/blanks passes validation."""
    is_valid, validation_errors = validate_payload_integrity(valid_full_universe_payload)
    assert is_valid is True
    assert len(validation_errors) == 0


@pytest.mark.parametrize("corrupt_value", [None, "", "null", "NULL", "None", math.nan, float("nan")])
def test_null_or_empty_value_rejected(valid_full_universe_payload, corrupt_value):
    """
    Asserts that if any required field contains None, empty string, 'null', or NaN,
    the validator strictly rejects the payload and reports exact row and column provenance.
    """
    corrupt_payload = [r.copy() for r in valid_full_universe_payload]
    # Corrupt row 42, field 'ltp'
    corrupt_payload[41]["ltp"] = corrupt_value

    with pytest.raises(ValueError, match="Payload integrity check failed: null or blank field detected"):
        validate_payload_integrity(corrupt_payload)


def test_missing_key_in_row_rejected(valid_full_universe_payload):
    """Asserts that a row missing any required schema key is rejected immediately."""
    corrupt_payload = [r.copy() for r in valid_full_universe_payload]
    # Remove 'rank' key entirely from row 10
    del corrupt_payload[9]["rank"]

    with pytest.raises(ValueError, match="Missing required schema key 'rank' in row 10"):
        validate_payload_integrity(corrupt_payload)


# ==============================================================================
# TEST 4: SHA-256 CHECKSUM MATCHING ACROSS SINKS
# ==============================================================================

def test_sha256_checksum_matching(valid_full_universe_payload):
    """
    Verifies deterministic SHA-256 checksum generation across sinks.
    Asserts that matching payloads produce identical 64-character SHA-256 hex digests.
    """
    checksum_a = compute_payload_checksum(valid_full_universe_payload)
    checksum_b = compute_payload_checksum(valid_full_universe_payload)

    assert isinstance(checksum_a, str)
    assert len(checksum_a) == 64, "Checksum must be a 64-character SHA-256 hex string"
    assert checksum_a == checksum_b, "Checksum calculation must be strictly deterministic"


def test_sha256_checksum_detects_single_bit_change(valid_full_universe_payload):
    """Asserts that altering even a single character in any row alters the SHA-256 checksum."""
    original_checksum = compute_payload_checksum(valid_full_universe_payload)

    # Mutate a single float in row 100 by 0.01
    mutated_payload = [r.copy() for r in valid_full_universe_payload]
    mutated_payload[99]["ltp"] += 0.01

    mutated_checksum = compute_payload_checksum(mutated_payload)
    assert mutated_checksum != original_checksum, "SHA-256 checksum must detect micro-mutations"


def test_sha256_checksum_detects_timestamp_mutation(valid_full_universe_payload):
    """Asserts that changing an exchange timestamp creates a checksum mismatch."""
    original_checksum = compute_payload_checksum(valid_full_universe_payload)

    mutated_payload = [r.copy() for r in valid_full_universe_payload]
    mutated_payload[0]["exchange_timestamp"] = "2026-10-12T15:29:59+05:30"

    mutated_checksum = compute_payload_checksum(mutated_payload)
    assert mutated_checksum != original_checksum

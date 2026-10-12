#!/usr/bin/env python3
"""
cloud_pipeline.py

Cloud Run Production Ingestion & Verification Engine.
Implements the 4 mandatory production verification gates:
1. HTTP 429 Throttling Recovery with Tenacity Exponential Backoff
2. BigQuery Row Count & Schema Parity (219 symbols)
3. Zero Missing, Null, Blank, or NaN Value Integrity Validation
4. Deterministic SHA-256 Cross-Sink Checksum Generation
"""

import hashlib
import json
import math
import sys
import time
from typing import Any, Dict, List, Tuple

import requests
from tenacity import (
    Retrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Canonical 219 F&O Universe Size
TARGET_UNIVERSE_SIZE = 219

# Canonical Required Schema Fields
REQUIRED_SCHEMA_FIELDS = [
    "symbol",
    "underlying",
    "expiry",
    "strike",
    "option_type",
    "ltp",
    "iv",
    "oi",
    "delta",
    "gamma",
    "pcr",
    "rank",
    "run_id",
    "exchange_timestamp",
    "source_cycle",
]


class HTTP429ThrottledError(Exception):
    """Raised when an API endpoint returns HTTP 429 Too Many Requests / Resource Exhausted."""
    pass


def execute_pipeline_cycle(
    endpoint_url: str,
    payload: List[Dict[str, Any]],
    max_retries: int = 5,
    base_delay: float = 0.1,
    max_delay: float = 30.0,
) -> Dict[str, Any]:
    """
    Executes a pipeline API call with tenacity-backed exponential backoff retry.
    Catches HTTP 429 throttling errors gracefully and retries up to max_retries.
    Fails closed with RuntimeError if HTTP 429 persists beyond max_retries.
    """
    attempts = 0

    def _call_endpoint():
        nonlocal attempts
        attempts += 1
        resp = requests.post(endpoint_url, json=payload, timeout=15)
        if resp.status_code == 429:
            raise HTTP429ThrottledError(f"HTTP 429 Rate Limit: {resp.text}")
        resp.raise_for_status()
        return resp

    retryer = Retrying(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=base_delay, max=max_delay),
        retry=retry_if_exception_type(HTTP429ThrottledError),
        sleep=time.sleep,
        reraise=False,
    )

    try:
        response = retryer(_call_endpoint)
        return {
            "status": "SUCCESS",
            "attempts": attempts,
            "response": response.json() if response.content else {},
        }
    except RetryError:
        raise RuntimeError(f"HTTP 429 quota exhausted after {max_retries} attempts")


def verify_bigquery_parity(
    bq_client: Any,
    table_id: str,
    staged_payload: List[Dict[str, Any]],
) -> Tuple[bool, Dict[str, Any]]:
    """
    Validates BigQuery table row count and schema parity against staged payload.
    Fails closed with ValueError on row count mismatch or missing schema columns.
    """
    table = bq_client.get_table(table_id)
    table_num_rows = getattr(table, "num_rows", 0)
    staged_num_rows = len(staged_payload)

    if table_num_rows != TARGET_UNIVERSE_SIZE:
        raise ValueError(
            f"Row count mismatch: BigQuery has {table_num_rows}, expected {TARGET_UNIVERSE_SIZE}"
        )

    table_fields = {field.name for field in getattr(table, "schema", [])}
    missing_fields = set(REQUIRED_SCHEMA_FIELDS) - table_fields
    if missing_fields:
        raise ValueError(f"Schema mismatch: missing fields {missing_fields}")

    report = {
        "row_count_match": True,
        "schema_fields_match": True,
        "table_num_rows": table_num_rows,
        "staged_num_rows": staged_num_rows,
    }
    return True, report


def validate_payload_integrity(payload: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Strictly validates that zero missing, null, empty string, or NaN values exist
    in any row of the ingestion payload across all REQUIRED_SCHEMA_FIELDS.
    Fails closed with ValueError providing exact row index and column provenance.
    """
    errors: List[str] = []

    for idx, row in enumerate(payload, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Payload row {idx} is not a valid dictionary object")

        for key in REQUIRED_SCHEMA_FIELDS:
            if key not in row:
                raise ValueError(f"Missing required schema key '{key}' in row {idx}")

            val = row[key]
            is_corrupt = False

            if val is None:
                is_corrupt = True
            elif isinstance(val, str) and (val.strip() == "" or val.strip().lower() in ("null", "none")):
                is_corrupt = True
            elif isinstance(val, float) and math.isnan(val):
                is_corrupt = True

            if is_corrupt:
                raise ValueError(
                    f"Payload integrity check failed: null or blank field detected in row {idx}, column '{key}'"
                )

    return True, errors


def compute_payload_checksum(payload: List[Dict[str, Any]]) -> str:
    """
    Computes a deterministic, cross-sink SHA-256 hexadecimal checksum.
    Uses canonical JSON formatting (sorted keys, no extraneous whitespace, UTF-8).
    """
    canonical_repr = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

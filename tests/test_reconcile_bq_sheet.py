"""
tests/test_reconcile_bq_sheet.py

Tests for scripts/reconcile_bq_sheet.py deterministic reconciliation engine.
"""

import os
import pytest
from scripts.reconcile_bq_sheet import (
    normalize_symbol,
    normalize_price,
    parse_timestamp,
    reconcile_records,
)


def test_normalize_symbol():
    assert normalize_symbol(" reliance ") == "RELIANCE"
    assert normalize_symbol("INFY") == "INFY"
    assert normalize_symbol(None) == ""


def test_normalize_price():
    assert normalize_price("1,040.50") == 1040.50
    assert normalize_price("₹2,500.00") == 2500.00
    assert normalize_price(152.9) == 152.9
    assert normalize_price("") is None
    assert normalize_price(None) is None
    assert normalize_price("invalid") is None


def test_parse_timestamp():
    # ISO 8601 with offset
    dt1 = parse_timestamp("2026-10-01T11:45:00+00:00")
    assert dt1 is not None
    assert dt1.hour == 11

    # Naive IST string
    dt2 = parse_timestamp("2026-10-01 17:15:00 IST")
    assert dt2 is not None
    # 17:15 IST is 11:45 UTC
    assert dt2.hour == 11
    assert dt2.minute == 45


def test_reconcile_records_all_categories():
    bq_records = [
        {"symbol": "RELIANCE", "spot_ltp": 2950.0, "snapshot_timestamp": "2026-10-01T11:45:00+00:00", "action_rating": "BUY"},
        {"symbol": "TCS", "spot_ltp": 4200.0, "snapshot_timestamp": "2026-10-01T11:45:00+00:00", "action_rating": "HOLD"},
        {"symbol": "INFY", "spot_ltp": 1900.0, "snapshot_timestamp": "2026-10-01T11:45:00+00:00", "action_rating": "BUY"}, # Price mismatch
        {"symbol": "HDFCBANK", "spot_ltp": 1650.0, "snapshot_timestamp": "2026-10-01T11:45:00+00:00", "action_rating": "BUY"}, # Time mismatch
        {"symbol": "WIPRO", "spot_ltp": 540.0, "snapshot_timestamp": "2026-10-01T11:45:00+00:00", "action_rating": "SELL"}, # BQ Only
    ]

    sheet_records = [
        {"symbol": "RELIANCE", "fut_ltp": "2,950.00", "timestamp_ist": "2026-10-01 17:15:00", "forensic_action_signal": "BUY"}, # MATCH
        {"symbol": "TCS", "fut_ltp": "4,200.00", "timestamp_ist": "2026-10-01 17:15:00", "forensic_action_signal": "HOLD"}, # MATCH
        {"symbol": "INFY", "fut_ltp": "2,100.00", "timestamp_ist": "2026-10-01 17:15:00", "forensic_action_signal": "BUY"}, # VALUE_MISMATCH (> 0.5%)
        {"symbol": "HDFCBANK", "fut_ltp": "1,650.00", "timestamp_ist": "2026-10-01 19:30:00", "forensic_action_signal": "BUY"}, # TIMESTAMP_MISMATCH (> 300s)
        {"symbol": "SBIN", "fut_ltp": "820.00", "timestamp_ist": "2026-10-01 17:15:00", "forensic_action_signal": "BUY"}, # SHEET Only
    ]

    result = reconcile_records(bq_records, sheet_records, price_tol_pct=0.5, time_tol_sec=300)
    summary = result["summary"]

    assert summary["total_keys_evaluated"] == 6
    assert summary["match_count"] == 2 # RELIANCE, TCS
    assert summary["bq_only_count"] == 1 # WIPRO
    assert summary["sheet_only_count"] == 1 # SBIN
    assert summary["value_mismatch_count"] == 1 # INFY
    assert summary["timestamp_mismatch_count"] == 1 # HDFCBANK

    # Verify authoritativeness metadata
    assert "primary_producer" in result["authoritativeness"]
    assert "reconciliation_rule" in result["authoritativeness"]


def test_reconcile_records_empty_handling():
    result = reconcile_records([], [])
    assert result["summary"]["total_keys_evaluated"] == 0
    assert result["summary"]["match_count"] == 0
    assert result["summary"]["match_pct"] == 0.0

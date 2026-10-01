"""
tests/test_reconcile_bq_sheet.py

Tests for scripts/reconcile_bq_sheet.py deterministic reconciliation engine.
Tests contract-level composite keys:
- timestamp / snapshot ID
- symbol
- expiry
- strike
- side / contract
And reports:
- BQ_ONLY
- SHEET_ONLY
- MATCH
- VALUE_MISMATCH
- TIMESTAMP_MISMATCH
"""

import os
import pytest
from scripts.reconcile_bq_sheet import (
    normalize_symbol,
    normalize_price,
    parse_timestamp,
    extract_snapshot_id,
    explode_option_contracts,
    reconcile_contract_level,
    reconcile_records,
    detect_header_row,
)


def test_detect_header_row_dynamically():
    # Case 1: Header at Row 0 (index 0 / Row 1)
    grid_row1 = [
        ["Symbol", "Nearest Expiry", "Fut LTP", "ATM Strike", "CE LTP", "PE LTP"],
        ["ABB", "2026-10-29", "6948.5", "6950", "145.2", "132.8"],
    ]
    assert detect_header_row(grid_row1) == 0

    # Case 2: Header at Row 1 (index 1 / Row 2, Row 0 is disclaimer banner)
    grid_row2 = [
        ["Measured CE/PE rank. No predicted gain percent. Alerts are not orders.", "", "", "", ""],
        ["Rank time IST", "Symbol", "Fut LTP", "ATM Strike", "CE LTP", "PE LTP", "Ranking Category"],
        ["2026-10-01 11:45:00", "ABB", "6948.5", "6950", "145.2", "132.8", "TOP_10"],
    ]
    assert detect_header_row(grid_row2) == 1

    # Case 3: Header at Row 2 (index 2 / Row 3, Rows 0-1 are title + subtitle)
    grid_row3 = [
        ["MEASURED PAPER OUTCOMES", "", "", "", ""],
        ["Counts only PAPER_ALERT_LOG rows with valid session prints. No sample trades written.", "", "", ""],
        ["Session Date", "Total Paper Alerts", "Settled Trades", "Wins", "Losses", "Win Rate %"],
        ["2026-09-28", "279", "279", "184", "95", "65.9%"],
    ]
    assert detect_header_row(grid_row3) == 2

    # Case 4: Header at Row 3 (index 3 / Row 4, Rows 0-2 are title banner + metadata + spacer)
    grid_row4 = [
        ["⚡ DYNAMIC OPTION CE/PE PREDICTION ENGINE", "", "", "", ""],
        ["Last Synced: 2026-10-01 11:45:00 IST", "Broker: CONNECTED", "Symbols: 219", ""],
        ["", "", "", "", ""],
        ["Rank", "Symbol", "Spot LTP", "Target Open Strike", "Expected Gap %", "Pre-Open Conviction %"],
        ["1", "ABB", "6948.5", "7000", "+1.85%", "88.5%"],
    ]
    assert detect_header_row(grid_row4) == 3


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


def test_extract_snapshot_id():
    snap1 = extract_snapshot_id("2026-10-01 11:45:00.452891+00:00")
    snap2 = extract_snapshot_id("2026-10-01 17:15:00 IST")
    assert snap1 == "2026-10-01T11:45Z"
    assert snap2 == "2026-10-01T11:45Z"
    assert snap1 == snap2  # UTC and IST resolve to identical snapshot bucket


def test_explode_option_contracts():
    wide_row = {
        "symbol": "ABB",
        "snapshot_timestamp": "2026-10-01 11:45:00+00:00",
        "expiry": "2026-10-29",
        "atm_strike": 6950,
        "atm_ce_contract": "ABB26OCT6950CE",
        "ce_ltp": 145.2,
        "ce_oi": 50000,
        "atm_pe_contract": "ABB26OCT6950PE",
        "pe_ltp": 132.8,
        "pe_oi": 42000,
    }
    contracts = explode_option_contracts([wide_row])
    assert len(contracts) == 2
    assert contracts[0]["side"] == "CE"
    assert contracts[0]["contract"] == "ABB26OCT6950CE"
    assert contracts[0]["price"] == 145.2
    assert contracts[1]["side"] == "PE"
    assert contracts[1]["contract"] == "ABB26OCT6950PE"
    assert contracts[1]["price"] == 132.8


def test_reconcile_contract_level_composite_keys():
    # BigQuery option snapshot
    bq_raw = [
        # 1 & 2: MATCH (CE & PE)
        {
            "symbol": "ABB",
            "snapshot_timestamp": "2026-10-01 11:45:00+00:00",
            "expiry": "2026-10-29",
            "atm_strike": 6950,
            "atm_ce_contract": "ABB26OCT6950CE",
            "ce_ltp": 145.0,
            "atm_pe_contract": "ABB26OCT6950PE",
            "pe_ltp": 130.0,
        },
        # 3 & 4: VALUE_MISMATCH on CE, MATCH on PE
        {
            "symbol": "RELIANCE",
            "snapshot_timestamp": "2026-10-01 11:45:00+00:00",
            "expiry": "2026-10-29",
            "atm_strike": 2950,
            "atm_ce_contract": "RELIANCE26OCT2950CE",
            "ce_ltp": 65.0,
            "atm_pe_contract": "RELIANCE26OCT2950PE",
            "pe_ltp": 50.0,
        },
        # 5 & 6: TIMESTAMP_MISMATCH (BQ snapshot from 08:00 UTC vs Sheet from 11:45 UTC)
        {
            "symbol": "TCS",
            "snapshot_timestamp": "2026-10-01 08:00:00+00:00",
            "expiry": "2026-10-29",
            "atm_strike": 4200,
            "atm_ce_contract": "TCS26OCT4200CE",
            "ce_ltp": 80.0,
            "atm_pe_contract": "TCS26OCT4200PE",
            "pe_ltp": 75.0,
        },
        # 7 & 8: BQ_ONLY
        {
            "symbol": "INFY",
            "snapshot_timestamp": "2026-10-01 11:45:00+00:00",
            "expiry": "2026-10-29",
            "atm_strike": 1900,
            "atm_ce_contract": "INFY26OCT1900CE",
            "ce_ltp": 35.0,
            "atm_pe_contract": "INFY26OCT1900PE",
            "pe_ltp": 30.0,
        },
    ]

    # Google Sheet FORENSIC_LIVE snapshot
    sheet_raw = [
        # 1 & 2: MATCH (CE & PE)
        {
            "symbol": "ABB",
            "timestamp_ist": "2026-10-01 17:15:00",  # Matches 11:45:00 UTC
            "nearest_expiry": "2026-10-29",
            "atm_strike": "6,950",
            "atm_ce_contract": "ABB26OCT6950CE",
            "ce_ltp": "145.00",
            "atm_pe_contract": "ABB26OCT6950PE",
            "pe_ltp": "130.00",
        },
        # 3 & 4: CE has price mismatch (75.0 vs 65.0), PE matches (50.0)
        {
            "symbol": "RELIANCE",
            "timestamp_ist": "2026-10-01 17:15:00",
            "nearest_expiry": "2026-10-29",
            "atm_strike": "2,950",
            "atm_ce_contract": "RELIANCE26OCT2950CE",
            "ce_ltp": "75.00",  # Price mismatch
            "atm_pe_contract": "RELIANCE26OCT2950PE",
            "pe_ltp": "50.00",  # MATCH
        },
        # 5 & 6: TIMESTAMP_MISMATCH
        {
            "symbol": "TCS",
            "timestamp_ist": "2026-10-01 17:15:00",  # 11:45 UTC vs BQ 08:00 UTC
            "nearest_expiry": "2026-10-29",
            "atm_strike": "4,200",
            "atm_ce_contract": "TCS26OCT4200CE",
            "ce_ltp": "80.00",
            "atm_pe_contract": "TCS26OCT4200PE",
            "pe_ltp": "75.00",
        },
        # SHEET_ONLY: WIPRO
        {
            "symbol": "WIPRO",
            "timestamp_ist": "2026-10-01 17:15:00",
            "nearest_expiry": "2026-10-29",
            "atm_strike": "540",
            "atm_ce_contract": "WIPRO26OCT540CE",
            "ce_ltp": "12.00",
            "atm_pe_contract": "WIPRO26OCT540PE",
            "pe_ltp": "10.00",
        },
    ]

    bq_contracts = explode_option_contracts(bq_raw)
    sheet_contracts = explode_option_contracts(sheet_raw)

    result = reconcile_contract_level(bq_contracts, sheet_contracts, price_tol_pct=0.5, time_tol_sec=300)
    summary = result["summary"]

    # Verify counts:
    # MATCH: ABB CE, ABB PE, RELIANCE PE (3 contracts)
    assert summary["match_count"] == 3
    # VALUE_MISMATCH: RELIANCE CE (1 contract)
    assert summary["value_mismatch_count"] == 1
    # TIMESTAMP_MISMATCH: TCS CE, TCS PE (2 contracts)
    assert summary["timestamp_mismatch_count"] == 2
    # BQ_ONLY: INFY CE, INFY PE (2 contracts)
    assert summary["bq_only_count"] == 2
    # SHEET_ONLY: WIPRO CE, WIPRO PE (2 contracts)
    assert summary["sheet_only_count"] == 2

    # Verify authoritativeness notice
    assert "Neither BigQuery nor OPTION_SHEET is authoritative" in result["authoritativeness"]["reconciliation_rule"]


def test_reconcile_records_all_categories():
    bq_records = [
        {"symbol": "RELIANCE", "spot_ltp": 2950.0, "snapshot_timestamp": "2026-10-01T11:45:00+00:00", "action_rating": "BUY"},
        {"symbol": "TCS", "spot_ltp": 4200.0, "snapshot_timestamp": "2026-10-01T11:45:00+00:00", "action_rating": "HOLD"},
        {"symbol": "INFY", "spot_ltp": 1900.0, "snapshot_timestamp": "2026-10-01T11:45:00+00:00", "action_rating": "BUY"},
        {"symbol": "HDFCBANK", "spot_ltp": 1650.0, "snapshot_timestamp": "2026-10-01T11:45:00+00:00", "action_rating": "BUY"},
        {"symbol": "WIPRO", "spot_ltp": 540.0, "snapshot_timestamp": "2026-10-01T11:45:00+00:00", "action_rating": "SELL"},
    ]

    sheet_records = [
        {"symbol": "RELIANCE", "fut_ltp": "2,950.00", "timestamp_ist": "2026-10-01 17:15:00", "forensic_action_signal": "BUY"},
        {"symbol": "TCS", "fut_ltp": "4,200.00", "timestamp_ist": "2026-10-01 17:15:00", "forensic_action_signal": "HOLD"},
        {"symbol": "INFY", "fut_ltp": "2,100.00", "timestamp_ist": "2026-10-01 17:15:00", "forensic_action_signal": "BUY"},
        {"symbol": "HDFCBANK", "fut_ltp": "1,650.00", "timestamp_ist": "2026-10-01 19:30:00", "forensic_action_signal": "BUY"},
        {"symbol": "SBIN", "fut_ltp": "820.00", "timestamp_ist": "2026-10-01 17:15:00", "forensic_action_signal": "BUY"},
    ]

    result = reconcile_records(bq_records, sheet_records, price_tol_pct=0.5, time_tol_sec=300)
    summary = result["summary"]

    assert summary["total_keys_evaluated"] == 6
    assert summary["match_count"] == 2
    assert summary["bq_only_count"] == 1
    assert summary["sheet_only_count"] == 1
    assert summary["value_mismatch_count"] == 1
    assert summary["timestamp_mismatch_count"] == 1

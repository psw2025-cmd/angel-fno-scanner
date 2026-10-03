#!/usr/bin/env python3
"""Regression tests for runtime provenance and holiday/grid/BQ fixes."""
from datetime import datetime
from unittest.mock import MagicMock
import pytest

from gainers import market_is_open, NSE_HOLIDAYS_2026
from angel_prediction_engine import (
    is_market_open,
    is_pre_market_time,
    is_pre_close_time,
    is_morning_reconcile_time,
)
from scanner import write_grid


def test_market_timing_respects_nse_holidays():
    # 2026-10-02 is Mahatma Gandhi Jayanti (Friday)
    holiday_market_hours = datetime(2026, 10, 2, 11, 0)
    holiday_pre_market = datetime(2026, 10, 2, 8, 30)
    holiday_reconcile = datetime(2026, 10, 2, 9, 20)
    holiday_pre_close = datetime(2026, 10, 2, 15, 10)

    assert market_is_open(holiday_market_hours) is False
    assert is_market_open(holiday_market_hours) is False
    assert is_pre_market_time(holiday_pre_market) is False
    assert is_morning_reconcile_time(holiday_reconcile) is False
    assert is_pre_close_time(holiday_pre_close) is False

    # Normal trading day 2026-10-01 (Thursday)
    normal_market_hours = datetime(2026, 10, 1, 11, 0)
    normal_pre_market = datetime(2026, 10, 1, 8, 30)
    normal_reconcile = datetime(2026, 10, 1, 9, 20)
    normal_pre_close = datetime(2026, 10, 1, 15, 10)

    assert market_is_open(normal_market_hours) is True
    assert is_market_open(normal_market_hours) is True
    assert is_pre_market_time(normal_pre_market) is True
    assert is_morning_reconcile_time(normal_reconcile) is True
    assert is_pre_close_time(normal_pre_close) is True


def test_write_grid_prevents_grid_overflow_on_exact_match():
    # Simulate FORENSIC_LIVE sheet with 220 rows and 18 columns
    ws = MagicMock()
    ws.row_count = 220
    ws.col_count = 18

    # 1 header + 219 data rows = 220 rows
    rows = [["col" for _ in range(18)] for _ in range(220)]

    write_grid(ws, rows)

    ws.update.assert_called_once()
    # When row count equals dataset length, batch_clear should NOT be called
    ws.batch_clear.assert_not_called()


def test_write_grid_clears_bounded_leftover_rows():
    # Simulate sheet with 250 rows and 18 columns, writing 220 rows
    ws = MagicMock()
    ws.row_count = 250
    ws.col_count = 18

    rows = [["col" for _ in range(18)] for _ in range(220)]

    write_grid(ws, rows)

    ws.update.assert_called_once()
    # Should clear exactly A221:R250, NOT A221:ZZ
    ws.batch_clear.assert_called_once_with(["A221:R250"])


def test_bigquery_write_truncate_config_validity():
    from google.cloud import bigquery

    # Verify that LoadJobConfig with WRITE_TRUNCATE without schema_update_options is valid
    cfg = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True,
    )
    assert cfg.write_disposition == bigquery.WriteDisposition.WRITE_TRUNCATE
    assert cfg.schema_update_options is None

"""Regression tests for exchange-timestamp freshness on intraday PAPER writes."""
import datetime as dt

import pytest

from tools.cycle_metadata import require_intraday_freshness

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 22, 4, 0, tzinfo=UTC)


def metadata(stamp):
    return {
        "source_timestamp": stamp.isoformat(),
        "run_id": "paper-run-1",
        "git_sha": "test-sha",
        "cycle_id": "test-cycle",
        "market_session": "EOD",
        "data_freshness_status": "EXCHANGE_VERIFIED",
    }


def test_recent_exchange_tick_passes_open_gate_even_if_workflow_session_eod():
    result = require_intraday_freshness(metadata(NOW - dt.timedelta(seconds=30)), now=NOW)
    assert result["status"] == "PASS"
    assert result["max_age_seconds"] == 120


def test_previous_session_tick_fails_open_gate_even_if_workflow_session_eod():
    with pytest.raises(ValueError, match="source timestamp out of range"):
        require_intraday_freshness(metadata(NOW - dt.timedelta(hours=18)), now=NOW)


def test_future_exchange_tick_fails_closed():
    with pytest.raises(ValueError, match="source timestamp out of range"):
        require_intraday_freshness(metadata(NOW + dt.timedelta(seconds=60)), now=NOW)


def test_missing_provenance_fails_closed():
    m = metadata(NOW)
    m["run_id"] = ""
    with pytest.raises(ValueError, match="missing cycle identity"):
        require_intraday_freshness(m, now=NOW)

"""Regression tests for PAPER schema enforcement, currency sanitization, and anomaly quarantine."""
from datetime import datetime
import pytest

from paper_log import (
    parse_percentage_change,
    measured_outcomes_with_quarantine,
    summarize_outcomes,
    render_production_sheet,
)


def test_parse_percentage_change_valid():
    assert parse_percentage_change("2.5") == 2.5
    assert parse_percentage_change("-1.45") == -1.45
    assert parse_percentage_change(0.0) == 0.0
    assert parse_percentage_change("0") == 0.0


def test_parse_percentage_change_sanitization():
    # Strips currency symbols, percent signs, commas
    assert parse_percentage_change("\u20b93.45") == 3.45
    assert parse_percentage_change("-\u20b91.49") == -1.49
    assert parse_percentage_change("$5.20") == 5.20
    assert parse_percentage_change("+2.06%") == 2.06
    assert parse_percentage_change("1,2.5%") == 12.5


def test_parse_percentage_change_rejects_anomalies():
    # Rejects extreme outlier numbers: lot sizes, spot prices, tokens
    assert parse_percentage_change("1820") is None  # Lot size
    assert parse_percentage_change("2775") is None  # Lot size / strike
    assert parse_percentage_change("1227.5") is None  # Spot / future price
    assert parse_percentage_change("343.59") is None  # > 35% anomaly
    assert parse_percentage_change("-100.0") is None  # > 35% anomaly
    assert parse_percentage_change("INVALID_TEXT") is None
    assert parse_percentage_change("") is None
    assert parse_percentage_change(None) is None


def test_measured_outcomes_quarantines_contaminated_rows():
    header = [
        "Logged at IST", "Session date", "Symbol", "Side", "Fut LTP", "Session change %",
        "CE contract", "PE contract", "Note", "Later session change %", "Outcome filled at",
    ]
    rows = [
        header,
        # Valid row 1: normal percentage
        ["2026-10-01 09:20:00", "2026-10-01", "RELIANCE", "CE", "2950", "1.2", "C", "P", "Note", "2.5", "2026-10-02 08:50:00"],
        # Valid row 2: normal percentage with PE
        ["2026-10-01 09:20:00", "2026-10-01", "INFY", "PE", "1850", "-0.8", "C", "P", "Note", "-1.5", "2026-10-02 08:50:00"],
        # Contaminated row 3: lot size in Session change % (1820)
        ["2026-09-28 05:24:59", "2026-09-28", "FORTIS", "PE", "837.8", "1820", "C", "P", "Note", "-0.6", "2026-09-29 08:50:16"],
        # Contaminated row 4: spot price in Session change % (1171.3)
        ["2026-09-28 02:50:05", "2026-09-28", "POLICYBZR", "PE", "1171.3", "1171.3", "C", "P", "Note", "-1.49", "2026-09-29 08:50:16"],
        # Contaminated row 5: non-numeric string
        ["2026-09-28 10:00:00", "2026-09-28", "TCS", "CE", "3500", "CORRUPTED", "C", "P", "Note", "1.0", "2026-09-29 08:50:16"],
    ]

    outcomes, quarantined = measured_outcomes_with_quarantine(rows)
    assert len(outcomes) == 2
    assert len(quarantined) == 3

    assert outcomes[0]["symbol"] == "RELIANCE"
    assert outcomes[1]["symbol"] == "INFY"

    quarantined_symbols = [q["symbol"] for q in quarantined]
    assert "FORTIS" in quarantined_symbols
    assert "POLICYBZR" in quarantined_symbols
    assert "TCS" in quarantined_symbols

    # Summary calculations are NOT corrupted by the 1820 lot size
    summary = summarize_outcomes(outcomes)
    assert summary["count"] == 2
    assert summary["wins"] == 2
    assert summary["win_rate"] == 1.0
    # Follow through is (2.5 - 1.2) = 1.3 for CE, and -((-1.5) - (-0.8)) = 0.7 for PE -> avg = 1.0
    assert abs(summary["average_follow_through"] - 1.0) < 1e-4


def test_render_production_sheet_records_quarantine_count():
    header = [
        "Logged at IST", "Session date", "Symbol", "Side", "Fut LTP", "Session change %",
        "CE contract", "PE contract", "Note", "Later session change %", "Outcome filled at",
    ]
    rows = [
        header,
        ["2026-10-01 09:20:00", "2026-10-01", "RELIANCE", "CE", "2950", "1.2", "C", "P", "Note", "2.5", "2026-10-02 08:50:00"],
        ["2026-09-28 05:24:59", "2026-09-28", "FORTIS", "PE", "837.8", "1820", "C", "P", "Note", "-0.6", "2026-09-29 08:50:16"],
    ]
    sheet = render_production_sheet(rows, datetime(2026, 10, 12, 12, 0))
    filled_row = next(r for r in sheet if r and r[0] == "Filled outcomes")
    quarantine_row = next(r for r in sheet if r and r[0] == "Quarantined outcomes")
    assert filled_row[1] == 1
    assert quarantine_row[1] == 1

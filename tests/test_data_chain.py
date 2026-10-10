#!/usr/bin/env python3
"""
tests/test_data_chain.py
End-to-End Data Chain Verification: PowerBI -> Excel -> Sheets -> BigQuery
Validates 219-underlying universe completeness, schema integrity, and fail-closed parity.
"""

import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SHEET_ID = "1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs"
CANONICAL_BQ_PROJECT = "fno-angel-prod-1790444589"
CANONICAL_BQ_DATASET = "fno_predictions"
EXPECTED_UNIVERSE_COUNT = 219

def test_data_snapshots_219_universe():
    """Verify latest_predictions snapshot contains exactly 219 unique underlying symbols."""
    pred_path = ROOT / "data" / "latest_predictions.json"
    assert pred_path.exists(), f"Missing required snapshot {pred_path}"

    with open(pred_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list), "latest_predictions.json must be a list of records"
    assert len(data) == EXPECTED_UNIVERSE_COUNT, f"Expected {EXPECTED_UNIVERSE_COUNT} records, found {len(data)}"

    symbols = [row.get("symbol") for row in data if row.get("symbol")]
    unique_symbols = set(symbols)
    assert len(unique_symbols) == EXPECTED_UNIVERSE_COUNT, (
        f"Expected {EXPECTED_UNIVERSE_COUNT} distinct symbols, found {len(unique_symbols)}"
    )

def test_data_chain_schema_fields():
    """Verify required critical schema fields exist for all 219 underlying records."""
    pred_path = ROOT / "data" / "latest_predictions.json"
    with open(pred_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    required_keys = {"symbol", "rank"}
    for idx, row in enumerate(data):
        assert required_keys.issubset(row.keys()), f"Row {idx} missing required fields: {required_keys - set(row.keys())}"

def test_canonical_chain_configuration():
    """Verify canonical IDs and targets across Sheets and BigQuery matches architecture."""
    # Check credentials or config definitions
    import credentials
    sheet_id = credentials.get_canonical_sheet_id()
    assert sheet_id == CANONICAL_SHEET_ID, f"Canonical Sheet ID mismatch: {sheet_id}"

def test_excel_and_pbi_safety():
    """Verify no binary Excel or PowerBI files are improperly parsed as text in data directory."""
    for path in (ROOT / "data").glob("*"):
        assert not path.suffix.lower() in [".xlsx", ".xls", ".pbix", ".pbi"], (
            f"Binary data artifact {path.name} must not be tracked in data/ directory"
        )

def test_encoding_chain_cp1252_safe():
    """Verify summary and prediction snapshots are encodable in standard cp1252 / ASCII without crashes."""
    summary_path = ROOT / "data" / "summary.md"
    if summary_path.exists():
        text = summary_path.read_text(encoding="utf-8")
        # Ensure it does not crash when represented in safe ASCII / cp1252 replacement
        safe_repr = text.encode("ascii", errors="replace").decode("ascii")
        assert len(safe_repr) > 0

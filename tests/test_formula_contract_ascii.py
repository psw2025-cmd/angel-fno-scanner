"""Regression: the Formula Checks OVERALL contract must be ASCII and match the live sheet text.

The live Google Sheet uses a plain hyphen. PM-001 forbids newly introduced non-ASCII source,
so the contract in tools/verify_harness.py uses a plain hyphen too. The formula is still
compared exactly by check_gate_formulas.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _contract_line():
    text = (ROOT / "tools" / "verify_harness.py").read_text(encoding="utf-8")
    lines = [l for l in text.splitlines() if "alerts are not live" in l]
    assert len(lines) == 1, "exactly one OVERALL contract line expected"
    return lines[0]


def test_overall_contract_is_ascii():
    line = _contract_line()
    assert all(ord(ch) < 128 for ch in line), "contract line must be ASCII (PM-001)"


def test_overall_contract_matches_live_sheet_text():
    line = _contract_line()
    assert 'MARKET CLOSED - alerts are not live' in line
    assert 'PASS - session open and gates clear' in line
    assert 'COUNTIF(E2:E6,"FAIL")+COUNTIF(E10:E11,"FAIL")>0,"BLOCKED"' in line

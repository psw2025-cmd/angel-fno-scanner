"""Offline regression checks for historical PAPER ledger semantics.

These checks do not prove current market freshness or broker-confirmed fills.
Run: python -m pytest -q tests/test_oms_net_pnl_contract.py
"""
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "scripts/sheets/reorganize_trader_terminal.py"


def test_ledger_net_pnl_uses_cost_adjusted_column():
    source = SOURCE.read_text(encoding="utf-8")
    assert "ROUND(SUM(P6:P),2)" in source
    assert 'net=f"=ROUND(N{i}-O{i},2)"' in source
    assert "Total Realized Net P&L" in source
    assert "ESTIMATED NSE taxes" in source
    assert "NOT BROKER-VERIFIED" in source


def test_ledger_readback_checks_costs_and_net():
    source = SOURCE.read_text(encoding="utf-8")
    assert 'expected_net=quantize(expected_gross-expected_fees)' in source
    assert 'raise RuntimeError(f"Financial readback mismatch at row {i}' in source
    assert 'raise RuntimeError("KPI net PnL does not reconcile")' in source

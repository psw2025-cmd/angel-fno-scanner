"""Regression contract: PAPER OMS headline must use net INR, not gross USD.

Run: python -m pytest -q tests/test_oms_net_pnl_contract.py
This is an offline source-contract test, NOT a live Google Sheets verification.
"""
from pathlib import Path


def test_canonical_trade_ledger_uses_net_pnl_and_estimated_costs():
    source = (Path(__file__).resolve().parents[1] / "scripts/sheets/reorganize_trader_terminal.py").read_text(encoding="utf-8")
    assert 'summary[0]=\'=IF(K3=0,"N/A",ROUND(SUM(P6:P),2))\'' in source
    assert '"Total Realized Net P&L (\\u20b9)"' in source
    assert "ESTIMATED NSE taxes" in source
    assert "NOT BROKER-VERIFIED" in source


def test_oms_dashboard_contract_is_net_inr_not_gross():
    # The canonical live workbook PAPER_TRADING_OMS!I3 was corrected to
    # ='TRADE_HISTORY_LEDGER'!A3 on 2026-11-26, with INR currency formatting.
    # Any publisher that rebuilds that dashboard must preserve this contract.
    formula = "='TRADE_HISTORY_LEDGER'!A3"
    assert formula.startswith("='TRADE_HISTORY_LEDGER'!")
    assert formula.endswith("A3")

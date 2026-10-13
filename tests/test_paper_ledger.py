"""Tests for deterministic quote-backed paper execution ledger and fee calculations."""
import pytest
from paper_ledger import (
    PaperTradeLedger,
    PaperTradeStatus,
    OptionDirection,
    compute_nse_option_fees,
)


def test_compute_nse_option_fees():
    # Buy INR 10,000, Sell INR 15,000
    fees = compute_nse_option_fees(buy_turnover=10000.0, sell_turnover=15000.0)
    assert fees.brokerage == 40.0  # 2 orders * INR 20
    assert fees.stt == 15.0  # 0.1% on INR 15,000 sell
    assert fees.exchange_charges == 12.5  # 0.05% on INR 25,000
    assert fees.stamp_duty == 0.3  # 0.003% on INR 10,000 buy
    assert fees.gst > 0.0
    assert fees.total_fees == round(fees.brokerage + fees.stt + fees.exchange_charges + fees.sebi_charges + fees.stamp_duty + fees.gst, 2)


def test_paper_signal_without_quote_fails_closed():
    ledger = PaperTradeLedger()
    trade = ledger.process_signal(
        signal_id="SIG-001",
        symbol="NIFTY",
        contract="NIFTY26OCT25000CE",
        direction=OptionDirection.BUY_CE,
        signal_timestamp_utc="2026-10-12T03:00:00Z",
        lot_size=25,
        lots=1,
        bid=None,
        ask=None,
        quote_timestamp=None,
        quote_source="NSE_DIRECT",
    )
    assert trade.status == PaperTradeStatus.UNFILLED_NO_QUOTE
    assert trade.fill_price is None
    assert trade.entry_turnover is None
    assert "imaginary fill rejected" in trade.status_reason.lower()


def test_paper_signal_with_wide_spread_is_rejected():
    ledger = PaperTradeLedger(max_spread_pct=0.10)
    # Bid 10, Ask 20 -> spread 10 / mid 15 = 66% > 10%
    trade = ledger.process_signal(
        signal_id="SIG-002",
        symbol="BANKNIFTY",
        contract="BANKNIFTY26OCT52000CE",
        direction=OptionDirection.BUY_CE,
        signal_timestamp_utc="2026-10-12T03:00:00Z",
        lot_size=15,
        lots=1,
        bid=10.0,
        ask=20.0,
        quote_timestamp="2026-10-12T03:00:00Z",
        quote_source="Angel_L2",
    )
    assert trade.status == PaperTradeStatus.REJECTED_ILLIQUID
    assert trade.fill_price is None


def test_paper_trade_lifecycle_fill_and_close():
    ledger = PaperTradeLedger(default_slippage=0.002)
    # Bid 100.0, Ask 101.0 -> Executed BUY at 101.0 * 1.002 = 101.20
    trade = ledger.process_signal(
        signal_id="SIG-003",
        symbol="TCS",
        contract="TCS26OCT3600CE",
        direction=OptionDirection.BUY_CE,
        signal_timestamp_utc="2026-10-12T04:00:00Z",
        lot_size=175,
        lots=1,
        bid=100.0,
        ask=101.0,
        quote_timestamp="2026-10-12T04:00:00Z",
        quote_source="Angel_L2",
    )
    assert trade.status == PaperTradeStatus.OPEN
    assert trade.fill_price == 101.20
    assert trade.quantity == 175
    assert trade.entry_turnover == round(101.20 * 175, 2)

    # Close with profit: Bid 120.0, Ask 121.0 -> Sold at 120.0 * (1 - 0.002) = 119.76
    closed_trade = ledger.close_trade(
        trade_id=trade.trade_id,
        exit_bid=120.0,
        exit_ask=121.0,
        exit_quote_timestamp="2026-10-12T08:00:00Z",
        exit_reason="TARGET_HIT",
    )
    assert closed_trade.status == PaperTradeStatus.CLOSED
    assert closed_trade.exit_price == 119.76
    assert closed_trade.gross_pnl > 0
    assert closed_trade.net_pnl < closed_trade.gross_pnl  # fees deducted
    assert closed_trade.fees.total_fees > 0

    summary = ledger.summary()
    assert summary["closed_trades"] == 1
    assert summary["wins"] == 1
    assert summary["win_rate"] == 1.0
    assert summary["total_net_pnl"] == closed_trade.net_pnl

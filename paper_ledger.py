"""Deterministic quote-backed PAPER execution ledger for Angel One F&O options.

Separates raw signals/alerts from quote-backed executable fills.
Enforces strictly zero backfill of imaginary actuals without fresh exchange quotes.
Models realistic transaction costs, slippage, spread, and exchange fees.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from enum import Enum
import hashlib
import math
from typing import Optional, Sequence, Dict, Any


class PaperTradeStatus(str, Enum):
    UNFILLED_NO_QUOTE = "UNFILLED_NO_QUOTE"
    REJECTED_ILLIQUID = "REJECTED_ILLIQUID"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"


class OptionDirection(str, Enum):
    BUY_CE = "BUY_CE"
    BUY_PE = "BUY_PE"


@dataclasses.dataclass(frozen=True)
class FeeBreakdown:
    brokerage: float
    stt: float
    exchange_charges: float
    sebi_charges: float
    stamp_duty: float
    gst: float
    total_fees: float


def compute_nse_option_fees(
    buy_turnover: float,
    sell_turnover: float,
    orders_count: int = 2,
    brokerage_per_order: float = 20.0,
) -> FeeBreakdown:
    """Compute realistic NSE statutory charges, brokerage, and taxes for options trades."""
    # Brokerage: flat per order (standard discount broker model)
    brokerage = float(orders_count * brokerage_per_order)
    
    # STT: 0.1% on option sell turnover (exercised / squared off premium)
    stt = round(sell_turnover * 0.001, 2)
    
    # Exchange turnover charges: 0.05% (NSE rate for options)
    exchange_charges = round((buy_turnover + sell_turnover) * 0.0005, 2)
    
    # SEBI turnover charge: INR 10 per crore (0.0001%)
    sebi_charges = round((buy_turnover + sell_turnover) * 0.000001, 2)
    
    # Stamp duty: 0.003% on buy value
    stamp_duty = round(buy_turnover * 0.00003, 2)
    
    # GST: 18% on (brokerage + exchange charges + sebi charges)
    gst = round((brokerage + exchange_charges + sebi_charges) * 0.18, 2)
    
    total_fees = round(brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst, 2)
    
    return FeeBreakdown(
        brokerage=brokerage,
        stt=stt,
        exchange_charges=exchange_charges,
        sebi_charges=sebi_charges,
        stamp_duty=stamp_duty,
        gst=gst,
        total_fees=total_fees,
    )


@dataclasses.dataclass
class PaperTrade:
    trade_id: str
    signal_id: str
    symbol: str
    contract: str
    direction: OptionDirection
    signal_timestamp_utc: str
    lot_size: int
    lots: int
    quantity: int
    
    # Entry Quote Provenance
    entry_bid: Optional[float]
    entry_ask: Optional[float]
    entry_quote_timestamp: Optional[str]
    entry_quote_source: Optional[str]
    
    # Execution
    fill_price: Optional[float]
    entry_slippage_rate: float
    entry_turnover: Optional[float]
    entry_filled_timestamp: Optional[str]
    status: PaperTradeStatus
    status_reason: str
    
    # Exit Execution (when closed)
    exit_bid: Optional[float] = None
    exit_ask: Optional[float] = None
    exit_price: Optional[float] = None
    exit_quote_timestamp: Optional[str] = None
    exit_filled_timestamp: Optional[str] = None
    exit_slippage_rate: float = 0.002
    exit_turnover: Optional[float] = None
    exit_reason: Optional[str] = None
    
    # P&L and Costs
    gross_pnl: Optional[float] = None
    net_pnl: Optional[float] = None
    fees: Optional[FeeBreakdown] = None
    return_pct: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        d["status"] = self.status.value
        d["direction"] = self.direction.value
        return d


class PaperTradeLedger:
    """Manages deterministic quote-backed PAPER trade lifecycle."""

    def __init__(self, default_slippage: float = 0.002, max_spread_pct: float = 0.15):
        self.default_slippage = default_slippage
        self.max_spread_pct = max_spread_pct
        self.trades: Dict[str, PaperTrade] = {}

    def process_signal(
        self,
        signal_id: str,
        symbol: str,
        contract: str,
        direction: OptionDirection,
        signal_timestamp_utc: str,
        lot_size: int,
        lots: int,
        bid: Optional[float],
        ask: Optional[float],
        quote_timestamp: Optional[str],
        quote_source: str,
    ) -> PaperTrade:
        """Process an alert signal into an executable trade or reject with proof."""
        trade_id = hashlib.sha256(f"{signal_id}:{contract}:{signal_timestamp_utc}".encode()).hexdigest()[:16]
        quantity = lot_size * lots

        # Guard: check quote presence
        if bid is None or ask is None or bid <= 0 or ask <= 0:
            trade = PaperTrade(
                trade_id=trade_id,
                signal_id=signal_id,
                symbol=symbol,
                contract=contract,
                direction=direction,
                signal_timestamp_utc=signal_timestamp_utc,
                lot_size=lot_size,
                lots=lots,
                quantity=quantity,
                entry_bid=bid,
                entry_ask=ask,
                entry_quote_timestamp=quote_timestamp,
                entry_quote_source=quote_source,
                fill_price=None,
                entry_slippage_rate=0.0,
                entry_turnover=None,
                entry_filled_timestamp=None,
                status=PaperTradeStatus.UNFILLED_NO_QUOTE,
                status_reason="Quote absent or zero; imaginary fill rejected",
            )
            self.trades[trade_id] = trade
            return trade

        # Guard: check spread reasonableness
        spread = ask - bid
        mid = (ask + bid) / 2.0
        spread_pct = spread / mid if mid > 0 else 1.0
        if spread_pct > self.max_spread_pct:
            trade = PaperTrade(
                trade_id=trade_id,
                signal_id=signal_id,
                symbol=symbol,
                contract=contract,
                direction=direction,
                signal_timestamp_utc=signal_timestamp_utc,
                lot_size=lot_size,
                lots=lots,
                quantity=quantity,
                entry_bid=bid,
                entry_ask=ask,
                entry_quote_timestamp=quote_timestamp,
                entry_quote_source=quote_source,
                fill_price=None,
                entry_slippage_rate=0.0,
                entry_turnover=None,
                entry_filled_timestamp=None,
                status=PaperTradeStatus.REJECTED_ILLIQUID,
                status_reason=f"Spread {spread_pct*100:.1f}% exceeds max liquid threshold {self.max_spread_pct*100:.1f}%",
            )
            self.trades[trade_id] = trade
            return trade

        # Execute simulated BUY fill at ASK + slippage
        fill_price = round(ask * (1.0 + self.default_slippage), 2)
        entry_turnover = round(fill_price * quantity, 2)
        now_utc = datetime.now(timezone.utc).isoformat()

        trade = PaperTrade(
            trade_id=trade_id,
            signal_id=signal_id,
            symbol=symbol,
            contract=contract,
            direction=direction,
            signal_timestamp_utc=signal_timestamp_utc,
            lot_size=lot_size,
            lots=lots,
            quantity=quantity,
            entry_bid=bid,
            entry_ask=ask,
            entry_quote_timestamp=quote_timestamp,
            entry_quote_source=quote_source,
            fill_price=fill_price,
            entry_slippage_rate=self.default_slippage,
            entry_turnover=entry_turnover,
            entry_filled_timestamp=now_utc,
            status=PaperTradeStatus.OPEN,
            status_reason="Executed at ASK with deterministic slippage",
        )
        self.trades[trade_id] = trade
        return trade

    def close_trade(
        self,
        trade_id: str,
        exit_bid: Optional[float],
        exit_ask: Optional[float],
        exit_quote_timestamp: Optional[str],
        exit_reason: str,
    ) -> PaperTrade:
        """Close an open trade using fresh market quote (selling at BID - slippage)."""
        trade = self.trades.get(trade_id)
        if not trade or trade.status != PaperTradeStatus.OPEN:
            raise ValueError(f"Trade {trade_id} is not in OPEN status")

        if exit_bid is None or exit_bid <= 0:
            # If quote is missing at exit, do not invent price
            trade.status_reason = f"Exit quote absent at {exit_reason}; trade kept OPEN"
            return trade

        # Selling at BID minus slippage
        exit_price = round(exit_bid * (1.0 - trade.exit_slippage_rate), 2)
        exit_turnover = round(exit_price * trade.quantity, 2)
        now_utc = datetime.now(timezone.utc).isoformat()

        gross_pnl = round(exit_turnover - trade.entry_turnover, 2)
        fees = compute_nse_option_fees(buy_turnover=trade.entry_turnover, sell_turnover=exit_turnover)
        net_pnl = round(gross_pnl - fees.total_fees, 2)
        return_pct = round((net_pnl / trade.entry_turnover) * 100.0, 2) if trade.entry_turnover > 0 else 0.0

        trade.exit_bid = exit_bid
        trade.exit_ask = exit_ask
        trade.exit_price = exit_price
        trade.exit_quote_timestamp = exit_quote_timestamp
        trade.exit_filled_timestamp = now_utc
        trade.exit_turnover = exit_turnover
        trade.exit_reason = exit_reason
        trade.gross_pnl = gross_pnl
        trade.net_pnl = net_pnl
        trade.fees = fees
        trade.return_pct = return_pct
        trade.status = PaperTradeStatus.CLOSED
        trade.status_reason = f"Closed at BID with slippage on {exit_reason}"

        return trade

    def summary(self) -> Dict[str, Any]:
        all_t = list(self.trades.values())
        closed = [t for t in all_t if t.status == PaperTradeStatus.CLOSED]
        wins = [t for t in closed if (t.net_pnl or 0) > 0]
        losses = [t for t in closed if (t.net_pnl or 0) < 0]
        total_net_pnl = round(sum(t.net_pnl or 0 for t in closed), 2)
        total_fees = round(sum(t.fees.total_fees if t.fees else 0 for t in closed), 2)

        return {
            "total_signals": len(all_t),
            "unfilled_no_quote": sum(1 for t in all_t if t.status == PaperTradeStatus.UNFILLED_NO_QUOTE),
            "rejected_illiquid": sum(1 for t in all_t if t.status == PaperTradeStatus.REJECTED_ILLIQUID),
            "open_trades": sum(1 for t in all_t if t.status == PaperTradeStatus.OPEN),
            "closed_trades": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(closed), 4) if closed else None,
            "total_net_pnl": total_net_pnl,
            "total_fees_paid": total_fees,
        }

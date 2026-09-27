"""Real NSE F&O gainers built only from quote fields.

Angel One FULL quotes supply price, previous close, change, volume, and open
interest. Black-76 IV, delta, and theta are the inversion of that premium.
Missing inputs stay blank. Nothing in this module invents a price target.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Iterable, Mapping, Sequence

DISCOUNT_RATE = 0.065
YEAR_SECONDS = 365.25 * 24 * 60 * 60
GAINER_ROW_LIMIT = 200
MIN_PREMIUM = 2.0
MIN_VOLUME = 100_000
MIN_OPEN_INTEREST = 5_000
HIGH_MOMENTUM_GAIN = 25.0
MAX_SPREAD_RATIO = 0.12

HEADERS = [
    "Contract",
    "Underlying",
    "Type",
    "Strike",
    "Expiry",
    "Live LTP",
    "Prev close",
    "Prev close basis",
    "Net chg",
    "Gain %",
    "Volume",
    "Open interest",
    "Best bid",
    "Best ask",
    "Intrinsic",
    "Time value",
    "Break-even",
    "Black-76 IV %",
    "Black-76 delta",
    "Black-76 theta per day",
    "Momentum",
    "Momentum basis",
    "Exchange time",
]


@dataclass(frozen=True)
class OptionQuote:
    contract: str
    underlying: str
    option_type: str
    strike: float
    expiry: date
    ltp: float
    prev_close: float | None
    prev_close_basis: str
    net_change: float | None
    gain_percent: float | None
    volume: float | None
    oi: float | None
    bid: float | None
    ask: float | None
    future_ltp: float | None
    exchange_time: str


def as_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def year_fraction(now: datetime, expiry: date) -> float:
    """Time left until 15:30 IST on the expiry date, as a year fraction."""
    expiry_at = datetime.combine(expiry, time(15, 30))
    seconds = (expiry_at - now.replace(tzinfo=None)).total_seconds()
    if seconds <= 0:
        return 0.0
    return seconds / YEAR_SECONDS


def black76_price(forward: float, strike: float, time_years: float, sigma: float, rate: float, is_call: bool) -> float:
    discount = math.exp(-rate * max(time_years, 0.0))
    intrinsic = max(0.0, (forward - strike) if is_call else (strike - forward))
    if time_years <= 0 or sigma <= 0 or forward <= 0 or strike <= 0:
        return discount * intrinsic
    vol_sqrt = sigma * math.sqrt(time_years)
    d1 = (math.log(forward / strike) + 0.5 * sigma * sigma * time_years) / vol_sqrt
    d2 = d1 - vol_sqrt
    if is_call:
        undiscounted = forward * _norm_cdf(d1) - strike * _norm_cdf(d2)
    else:
        undiscounted = strike * _norm_cdf(-d2) - forward * _norm_cdf(-d1)
    return discount * undiscounted


def black76_greeks(forward: float, strike: float, time_years: float, sigma: float, rate: float, is_call: bool) -> tuple[float, float] | None:
    """Return Black-76 delta and theta per calendar day, or None when undefined."""
    if time_years <= 0 or sigma <= 0 or forward <= 0 or strike <= 0:
        return None
    vol_sqrt = sigma * math.sqrt(time_years)
    d1 = (math.log(forward / strike) + 0.5 * sigma * sigma * time_years) / vol_sqrt
    d2 = d1 - vol_sqrt
    discount = math.exp(-rate * time_years)
    if is_call:
        delta = discount * _norm_cdf(d1)
        undiscounted = forward * _norm_cdf(d1) - strike * _norm_cdf(d2)
    else:
        delta = -discount * _norm_cdf(-d1)
        undiscounted = strike * _norm_cdf(-d2) - forward * _norm_cdf(-d1)
    price = discount * undiscounted
    # dPrice/dT. Calendar theta is that derivative times dT per day (-1/365.25).
    dprice_dt = (-rate * price) + discount * forward * _norm_pdf(d1) * sigma / (2.0 * math.sqrt(time_years))
    theta_per_day = dprice_dt * (-1.0 / 365.25)
    return delta, theta_per_day


def implied_vol(price: float, forward: float, strike: float, time_years: float, rate: float, is_call: bool) -> float | None:
    """Invert Black-76. Return None when the premium is outside the model."""
    if price <= 0 or forward <= 0 or strike <= 0 or time_years <= 0:
        return None
    discount = math.exp(-rate * time_years)
    intrinsic = discount * max(0.0, (forward - strike) if is_call else (strike - forward))
    if price <= intrinsic + 1e-8:
        return None
    low, high = 1e-4, 5.0
    if black76_price(forward, strike, time_years, high, rate, is_call) < price:
        return None
    for _ in range(80):
        mid = 0.5 * (low + high)
        if black76_price(forward, strike, time_years, mid, rate, is_call) > price:
            high = mid
        else:
            low = mid
    return 0.5 * (low + high)


def parse_expiry(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    for fmt in ("%d-%b-%Y", "%d%b%Y"):
        try:
            return datetime.strptime(text.upper(), fmt).date()
        except ValueError:
            continue
    return None


def market_is_open(now: datetime) -> bool:
    local = now.replace(tzinfo=None)
    if local.weekday() >= 5:
        return False
    minutes = local.hour * 60 + local.minute
    return (9 * 60 + 15) <= minutes <= (15 * 60 + 30)


def resolve_prev_close(ltp: float | None, close: float | None, net_change: float | None, gain_percent: float | None) -> tuple[float | None, str]:
    if close is not None and close > 0:
        return close, "Angel close"
    if ltp is not None and net_change is not None:
        previous = ltp - net_change
        if previous > 0:
            return previous, "Angel LTP minus Angel net change"
    if ltp is not None and gain_percent is not None and gain_percent > -100:
        previous = ltp / (1.0 + gain_percent / 100.0)
        if previous > 0:
            return previous, "Implied from Angel LTP and change %"
    return None, ""


def _best_depth_price(levels) -> float | None:
    if not isinstance(levels, list) or not levels:
        return None
    first = levels[0]
    if not isinstance(first, Mapping):
        return None
    price = as_float(first.get("price"))
    if price is None or price <= 0:
        return None
    return price


def quote_from_angel(raw: Mapping, meta: Mapping) -> OptionQuote | None:
    """Build one contract from an Angel FULL quote and scrip-master metadata."""
    ltp = as_float(raw.get("ltp"))
    if ltp is None or ltp <= 0:
        return None
    contract = str(meta.get("contract") or raw.get("tradingSymbol") or "").strip().upper()
    underlying = str(meta.get("underlying") or "").strip().upper()
    option_type = str(meta.get("option_type") or "").strip().upper()
    strike = as_float(meta.get("strike"))
    expiry = meta.get("expiry")
    if isinstance(expiry, str):
        expiry = parse_expiry(expiry)
    if not contract or " " in contract or option_type not in ("CE", "PE") or strike is None or strike <= 0 or not isinstance(expiry, date):
        return None
    close = as_float(raw.get("close"))
    net = as_float(raw.get("netChange"))
    gain = as_float(raw.get("percentChange"))
    previous, basis = resolve_prev_close(ltp, close if close and close > 0 else None, net, gain)
    if previous is not None:
        net = ltp - previous
    elif net is None and previous is None:
        net = None
    depth = raw.get("depth") if isinstance(raw.get("depth"), Mapping) else {}
    feed = str(raw.get("exchFeedTime") or raw.get("exchTradeTime") or "")
    return OptionQuote(
        contract=contract,
        underlying=underlying,
        option_type=option_type,
        strike=strike,
        expiry=expiry,
        ltp=ltp,
        prev_close=previous,
        prev_close_basis=basis,
        net_change=net,
        gain_percent=gain,
        volume=as_float(raw.get("tradeVolume")),
        oi=as_float(raw.get("opnInterest")),
        bid=_best_depth_price(depth.get("buy") if isinstance(depth, Mapping) else None),
        ask=_best_depth_price(depth.get("sell") if isinstance(depth, Mapping) else None),
        future_ltp=as_float(meta.get("future_ltp")),
        exchange_time=feed,
    )


def _column_index(header: Sequence[str], name: str) -> int | None:
    for index, cell in enumerate(header):
        if str(cell).strip().lower() == name.lower():
            return index
    return None


def _cell(row: Sequence, index: int | None):
    if index is None or index >= len(row):
        return None
    return row[index]


def contracts_from_forensic(values: Sequence[Sequence], exchange_time_fallback: str = "") -> list[OptionQuote]:
    """Turn FORENSIC_LIVE rows into CE and PE quotes. Volume is absent there, so it stays blank."""
    if not values:
        return []
    header = [str(cell) for cell in values[0]]
    columns = {name: _column_index(header, name) for name in (
        "Symbol",
        "Nearest Expiry",
        "Fut LTP",
        "ATM Strike",
        "ATM CE Contract",
        "CE LTP",
        "CE Chg %",
        "CE OI",
        "ATM PE Contract",
        "PE LTP",
        "PE Chg %",
        "PE OI",
        "Timestamp (IST)",
    )}
    quotes: list[OptionQuote] = []
    for row in values[1:]:
        if not row or not str(_cell(row, columns["Symbol"]) or "").strip():
            continue
        underlying = str(_cell(row, columns["Symbol"])).strip().upper()
        expiry = parse_expiry(_cell(row, columns["Nearest Expiry"]))
        strike = as_float(_cell(row, columns["ATM Strike"]))
        future_ltp = as_float(_cell(row, columns["Fut LTP"]))
        stamped = str(_cell(row, columns["Timestamp (IST)"]) or exchange_time_fallback)
        if expiry is None or strike is None or strike <= 0:
            continue
        sides = (
            ("CE", "ATM CE Contract", "CE LTP", "CE Chg %", "CE OI"),
            ("PE", "ATM PE Contract", "PE LTP", "PE Chg %", "PE OI"),
        )
        for option_type, contract_name, ltp_name, gain_name, oi_name in sides:
            contract = str(_cell(row, columns[contract_name]) or "").strip().upper()
            ltp = as_float(_cell(row, columns[ltp_name]))
            if not contract or " " in contract or ltp is None or ltp <= 0:
                continue
            gain = as_float(_cell(row, columns[gain_name]))
            previous, basis = resolve_prev_close(ltp, None, None, gain)
            net = (ltp - previous) if previous is not None else None
            quotes.append(OptionQuote(
                contract=contract,
                underlying=underlying,
                option_type=option_type,
                strike=strike,
                expiry=expiry,
                ltp=ltp,
                prev_close=previous,
                prev_close_basis=basis,
                net_change=net,
                gain_percent=gain,
                volume=None,
                oi=as_float(_cell(row, columns[oi_name])),
                bid=None,
                ask=None,
                future_ltp=future_ltp if future_ltp and future_ltp > 0 else None,
                exchange_time=stamped,
            ))
    return quotes


def classify_momentum(quote: OptionQuote, market_open: bool) -> tuple[str, str]:
    if not market_open:
        return (
            "MARKET CLOSED",
            "NSE F&O is closed. Gain % is the latest Angel change, not a live alert.",
        )
    if quote.ltp < MIN_PREMIUM:
        return (
            "THIN PREMIUM",
            "Live premium is below ₹2, so the percent change is not a momentum signal.",
        )
    if quote.volume is None or quote.oi is None or quote.volume < MIN_VOLUME or quote.oi < MIN_OPEN_INTEREST:
        return (
            "LOW LIQUIDITY",
            "Volume or open interest is missing or below the live-board floor.",
        )
    if quote.bid is not None and quote.ask is not None and quote.ask >= quote.bid and quote.ltp > 0:
        spread_ratio = (quote.ask - quote.bid) / quote.ltp
        if spread_ratio > MAX_SPREAD_RATIO:
            return (
                "WIDE SPREAD",
                "Best bid to ask is wider than 12% of the live premium.",
            )
    if quote.gain_percent is not None and quote.gain_percent >= HIGH_MOMENTUM_GAIN:
        return (
            "HIGH MOMENTUM",
            "Open session, Angel change at least 25%, premium at least ₹2, volume and open interest above the floor.",
        )
    return (
        "MEASURED",
        "Quote passed the liquidity floor and did not reach the 25% change rule.",
    )


def _intrinsic(quote: OptionQuote) -> float | None:
    if quote.future_ltp is None:
        return None
    if quote.option_type == "CE":
        return max(0.0, quote.future_ltp - quote.strike)
    return max(0.0, quote.strike - quote.future_ltp)


def _break_even(quote: OptionQuote) -> float | None:
    if quote.option_type == "CE":
        return quote.strike + quote.ltp
    return quote.strike - quote.ltp


def _model_fields(quote: OptionQuote, now: datetime) -> tuple[float | None, float | None, float | None, float | None, float | None]:
    intrinsic = _intrinsic(quote)
    time_value = (quote.ltp - intrinsic) if intrinsic is not None else None
    if quote.future_ltp is None:
        return intrinsic, time_value, None, None, None
    time_years = year_fraction(now, quote.expiry)
    sigma = implied_vol(
        quote.ltp,
        quote.future_ltp,
        quote.strike,
        time_years,
        DISCOUNT_RATE,
        quote.option_type == "CE",
    )
    if sigma is None:
        return intrinsic, time_value, None, None, None
    greeks = black76_greeks(
        quote.future_ltp,
        quote.strike,
        time_years,
        sigma,
        DISCOUNT_RATE,
        quote.option_type == "CE",
    )
    if greeks is None:
        return intrinsic, time_value, sigma * 100.0, None, None
    delta, theta = greeks
    return intrinsic, time_value, sigma * 100.0, delta, theta


def _round(value: float | None, digits: int):
    if value is None:
        return ""
    return round(value, digits)


def select_ranked(quotes: Iterable[OptionQuote], limit: int = GAINER_ROW_LIMIT) -> list[OptionQuote]:
    ranked = [quote for quote in quotes if quote.ltp > 0 and quote.gain_percent is not None and " " not in quote.contract]
    ranked.sort(key=lambda quote: quote.gain_percent if quote.gain_percent is not None else -10**9, reverse=True)
    return ranked[:limit]


def render_gainer_sheet(quotes: Iterable[OptionQuote], now: datetime, source: str) -> list[list]:
    """Rows for the gainers tab. Exchange fields come from the quote. Greeks are Black-76."""
    selected = select_ranked(quotes)
    open_session = market_is_open(now)
    session = "MARKET OPEN" if open_session else "MARKET CLOSED"
    high_momentum = 0
    rendered: list[list] = []
    for quote in selected:
        label, reason = classify_momentum(quote, open_session)
        if label == "HIGH MOMENTUM":
            high_momentum += 1
        intrinsic, time_value, iv, delta, theta = _model_fields(quote, now)
        rendered.append([
            quote.contract,
            quote.underlying,
            quote.option_type,
            quote.strike,
            quote.expiry.isoformat(),
            round(quote.ltp, 4),
            _round(quote.prev_close, 4),
            quote.prev_close_basis,
            _round(quote.net_change, 4),
            _round(quote.gain_percent, 4),
            "" if quote.volume is None else quote.volume,
            "" if quote.oi is None else quote.oi,
            _round(quote.bid, 4),
            _round(quote.ask, 4),
            _round(intrinsic, 4),
            _round(time_value, 4),
            _round(_break_even(quote), 4),
            _round(iv, 4),
            _round(delta, 4),
            _round(theta, 4),
            label,
            reason,
            quote.exchange_time,
        ])
    title = "F&O Options Top Gainers — Angel One quotes"
    note = (
        f"As of {now.strftime('%Y-%m-%d %H:%M:%S')} IST | {session} | "
        f"Rows {len(rendered)} | High momentum {high_momentum} | Source {source}. "
        "Prices, change, volume, and open interest are quote fields. "
        "Blank cells were missing from the feed. "
        "IV, delta, and theta are Black-76 at a 6.5% discount rate, inverted from the premium. "
        "No price target is calculated."
    )
    return [[title], [note], [], HEADERS, *rendered]


def window_strikes(strikes: Sequence[float], future_ltp: float | None, each_side: int) -> list[float]:
    ordered = sorted({float(strike) for strike in strikes if strike and float(strike) > 0})
    if not ordered or future_ltp is None or future_ltp <= 0 or each_side < 0:
        return []
    atm = min(ordered, key=lambda strike: abs(strike - future_ltp))
    center = ordered.index(atm)
    return ordered[max(0, center - each_side): center + each_side + 1]


def strike_window_tokens(strike_map: Mapping[float, Mapping], future_ltp: float | None, each_side: int) -> list[tuple[str, Mapping]]:
    """Return (token, meta) for CE and PE inside the strike window."""
    chosen = window_strikes(list(strike_map), future_ltp, each_side)
    pairs: list[tuple[str, Mapping]] = []
    for strike in chosen:
        contracts = strike_map.get(strike) or {}
        for option_type in ("CE", "PE"):
            contract = contracts.get(option_type)
            if not isinstance(contract, Mapping):
                continue
            token = str(contract.get("token") or "").strip()
            if not token:
                continue
            pairs.append((token, {
                "contract": contract.get("symbol"),
                "underlying": contract.get("name"),
                "option_type": option_type,
                "strike": strike,
                "expiry": contract.get("expiry"),
                "future_ltp": future_ltp,
            }))
    return pairs

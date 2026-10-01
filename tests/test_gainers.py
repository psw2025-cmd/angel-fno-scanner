from datetime import datetime

from gainers import (
    OptionQuote,
    black76_greeks,
    black76_price,
    classify_momentum,
    contracts_from_forensic,
    implied_vol,
    market_is_open,
    quote_from_angel,
    render_gainer_sheet,
    select_ranked,
    select_ranked_by_side,
    top_ce_pe_ranks,
    window_strikes,
    year_fraction,
)
from paper_log import alerts_to_append, fill_later_changes, render_production_sheet


NOW_CLOSED = datetime(2026, 9, 27, 17, 6, 4)  # Sunday
NOW_OPEN = datetime(2026, 9, 25, 10, 15, 0)  # Friday


def test_market_clock_matches_nse_session():
    assert market_is_open(NOW_CLOSED) is False
    assert market_is_open(NOW_OPEN) is True
    assert market_is_open(datetime(2026, 9, 25, 9, 14)) is False
    assert market_is_open(datetime(2026, 9, 25, 15, 40)) is True
    assert market_is_open(datetime(2026, 9, 25, 15, 41)) is False
    assert market_is_open(datetime(2026, 9, 26, 11, 0)) is False  # Saturday


def test_black76_iv_roundtrip_and_theta_sign():
    forward, strike, years, sigma, rate = 100.0, 100.0, 30 / 365.25, 0.22, 0.065
    price = black76_price(forward, strike, years, sigma, rate, True)
    solved = implied_vol(price, forward, strike, years, rate, True)
    assert solved is not None
    assert abs(solved - sigma) < 1e-4
    delta, theta = black76_greeks(forward, strike, years, sigma, rate, True)
    assert 0.3 < delta < 0.7
    put_delta, _ = black76_greeks(forward, strike, years, sigma, rate, False)
    assert -0.7 < put_delta < -0.3
    bumped = black76_price(forward, strike, years - 1 / 365.25, sigma, rate, True)
    finite_theta = bumped - price
    assert theta < 0
    assert abs(theta - finite_theta) < 0.05


def test_iv_is_blank_when_premium_is_below_intrinsic():
    solved = implied_vol(1.0, 100.0, 90.0, 0.05, 0.065, True)
    assert solved is None


def test_forensic_nhpc_replaces_the_scratchpad_contract():
    values = [[
        "Timestamp (IST)", "Symbol", "Nearest Expiry", "Fut LTP", "Fut Chg %", "Fut OBI",
        "ATM Strike", "ATM CE Contract", "CE LTP", "CE Chg %", "CE OI", "CE OBI",
        "ATM PE Contract", "PE LTP", "PE Chg %", "PE OI", "ATM PCR", "Forensic Action Signal",
    ], [
        "2026-09-27 17:06:04", "NHPC", "29-Sep-2026", 76.28, -0.1, -0.494,
        76, "NHPC29SEP2676CE", 0.63, -24.1, 1862600, -0.503,
        "NHPC29SEP2676PE", 0.37, -27.45, 2335200, 1.25, "NEUTRAL / CONSOLIDATION",
    ], [
        "2026-09-27 17:06:04", "KAYNES", "29-Sep-2026", 3646.8, 3.88, -0.888,
        3650, "KAYNES29SEP263650CE", 43.9, 248.41, 64800, -0.485,
        "KAYNES29SEP263650PE", 41.15, -72.57, 21450, 0.33, "NEUTRAL / CONSOLIDATION",
    ]]
    sheet = render_gainer_sheet(contracts_from_forensic(values), NOW_CLOSED, "FORENSIC_LIVE")
    flat = " ".join(str(cell) for row in sheet for cell in row)
    assert "NHPC 100 CE" not in flat
    assert "9.75" not in flat
    assert "HIGH MOMENTUM" not in flat
    assert "predicted" not in flat.lower()
    assert "econometric" not in flat.lower()
    assert "sample" not in flat.lower()
    contracts = [row[0] for row in sheet[4:]]
    assert contracts[0] == "KAYNES29SEP263650CE"
    nhpc = next(row for row in sheet[4:] if row[0] == "NHPC29SEP2676CE")
    assert nhpc[1] == "NHPC"
    assert nhpc[3] == 76
    assert nhpc[4] == "2026-09-29"
    assert nhpc[5] == 0.63
    assert nhpc[7] == "Implied from Angel LTP and change %"
    assert nhpc[9] == -24.1
    assert nhpc[10] == ""
    assert nhpc[11] == 1862600
    assert nhpc[20] == "MARKET CLOSED"
    assert isinstance(nhpc[17], float)  # IV inverted from 0.63, not a typed constant
    assert nhpc[17] != 83.1


def test_high_momentum_requires_an_open_liquid_quote():
    liquid = OptionQuote(
        contract="KAYNES29SEP263650CE",
        underlying="KAYNES",
        option_type="CE",
        strike=3650,
        expiry=NOW_OPEN.date().replace(day=29),
        ltp=43.9,
        prev_close=12.6,
        prev_close_basis="Angel close",
        net_change=31.3,
        gain_percent=248.41,
        volume=250000,
        oi=64800,
        bid=43.5,
        ask=44.2,
        future_ltp=3646.8,
        exchange_time="2026-09-25 10:15:00",
    )
    thin = OptionQuote(
        contract="MAHABANK29SEP2685CE",
        underlying="MAHABANK",
        option_type="CE",
        strike=85,
        expiry=liquid.expiry,
        ltp=0.69,
        prev_close=0.23,
        prev_close_basis="Angel close",
        net_change=0.46,
        gain_percent=200.0,
        volume=5_000_000,
        oi=2_632_500,
        bid=0.65,
        ask=0.70,
        future_ltp=84.81,
        exchange_time="2026-09-25 10:15:00",
    )
    closed_sheet = render_gainer_sheet([liquid, thin], NOW_CLOSED, "Angel FULL")
    assert all(row[20] == "MARKET CLOSED" for row in closed_sheet[4:])
    open_sheet = render_gainer_sheet([liquid, thin], NOW_OPEN, "Angel FULL")
    labels = {row[0]: row[20] for row in open_sheet[4:]}
    assert labels["KAYNES29SEP263650CE"] == "HIGH MOMENTUM"
    assert labels["MAHABANK29SEP2685CE"] == "THIN PREMIUM"
    assert sum(1 for row in open_sheet[4:] if row[20] == "HIGH MOMENTUM") == 1


def test_angel_full_quote_uses_exchange_close_and_depth():
    raw = {
        "ltp": 43.9,
        "close": 12.6,
        "netChange": 31.3,
        "percentChange": 248.41,
        "tradeVolume": 250000,
        "opnInterest": 64800,
        "exchFeedTime": "25-Sep-2026 10:15:01",
        "depth": {"buy": [{"price": 43.5, "quantity": 100}], "sell": [{"price": 44.2, "quantity": 80}]},
    }
    meta = {
        "contract": "KAYNES29SEP263650CE",
        "underlying": "KAYNES",
        "option_type": "CE",
        "strike": 3650,
        "expiry": "29-Sep-2026",
        "future_ltp": 3646.8,
    }
    quote = quote_from_angel(raw, meta)
    assert quote is not None
    assert quote.prev_close == 12.6
    assert quote.prev_close_basis == "Angel close"
    assert abs(quote.net_change - (43.9 - 12.6)) < 1e-9
    assert quote.volume == 250000
    assert quote.bid == 43.5
    assert quote.ask == 44.2
    assert quote_from_angel({"ltp": 0}, meta) is None
    spaced = dict(meta)
    spaced["contract"] = "KAYNES 3650 CE"
    assert quote_from_angel(raw, spaced) is None


def test_missing_gain_is_not_treated_as_zero():
    quote = OptionQuote(
        contract="NHPC29SEP2676CE",
        underlying="NHPC",
        option_type="CE",
        strike=76,
        expiry=NOW_CLOSED.date().replace(day=29),
        ltp=0.63,
        prev_close=None,
        prev_close_basis="",
        net_change=None,
        gain_percent=None,
        volume=10,
        oi=10,
        bid=None,
        ask=None,
        future_ltp=76.28,
        exchange_time="",
    )
    assert select_ranked([quote]) == []


def test_strike_window_follows_the_future():
    strikes = [70, 72.5, 75, 77.5, 80, 85]
    assert window_strikes(strikes, 76.2, 1) == [72.5, 75.0, 77.5]
    assert window_strikes(strikes, None, 2) == []


def test_year_fraction_ends_at_expiry_close():
    now = datetime(2026, 9, 29, 15, 40)
    assert year_fraction(now, now.date()) == 0
    earlier = datetime(2026, 9, 27, 15, 40)
    assert year_fraction(earlier, now.date()) == 2 / 365.25


def test_empty_paper_log_does_not_invent_a_win_rate():
    sheet = render_production_sheet([
        ["Logged at IST", "Session date", "Symbol", "Side", "Fut LTP", "Session change %",
         "CE contract", "PE contract", "Note", "Later session change %", "Outcome filled at"],
    ], NOW_CLOSED)
    flat = " ".join(str(cell) for row in sheet for cell in row)
    assert "85" not in flat
    assert "8.02" not in flat
    assert "586" not in flat
    assert "PT-1001" not in flat
    assert "sample" in flat.lower()  # the sentence that no sample trades are written
    win_row = next(row for row in sheet if row and row[0] == "Win rate")
    assert win_row[1] == ""
    assert alerts_to_append([], [{"symbol": "NHPC", "side": "CE", "fut_ltp": 76.28, "session_change": -0.1,
                                  "ce_contract": "NHPC29SEP2676CE", "pe_contract": "NHPC29SEP2676PE"}],
                            NOW_CLOSED, market_open=False) == []


def test_paper_log_appends_only_live_signals_and_fills_a_later_session():
    header = ["Logged at IST", "Session date", "Symbol", "Side", "Fut LTP", "Session change %",
              "CE contract", "PE contract", "Note", "Later session change %", "Outcome filled at"]
    added = alerts_to_append([header], [{
        "symbol": "KAYNES",
        "side": "CE",
        "fut_ltp": 3646.8,
        "session_change": 3.88,
        "ce_contract": "KAYNES29SEP263650CE",
        "pe_contract": "KAYNES29SEP263650PE",
    }], NOW_OPEN, market_open=True)
    assert len(added) == 1
    assert added[0][2] == "KAYNES"
    assert added[0][9] == ""
    again = alerts_to_append([header, added[0]], [{
        "symbol": "KAYNES", "side": "CE", "fut_ltp": 1, "session_change": 1,
        "ce_contract": "X", "pe_contract": "Y",
    }], NOW_OPEN, market_open=True)
    assert again == []
    filled = fill_later_changes([header, added[0]], {"KAYNES": 5.5}, datetime(2026, 9, 28, 10, 0))
    assert filled is not None
    assert filled[1][9] == 5.5
    sheet = render_production_sheet(filled, datetime(2026, 9, 28, 10, 0))
    win_row = next(row for row in sheet if row and row[0] == "Win rate")
    assert win_row[1] == 1.0


def test_ce_pe_rankings_are_independent_and_liquidity_gated():
    def q(contract, side, gain, bid, ask, volume=250000, oi=50000):
        return OptionQuote(
            contract=contract, underlying="TEST", option_type=side, strike=100,
            expiry=NOW_OPEN.date(), ltp=10.0, prev_close=10.0 / (1.0 + gain / 100.0),
            prev_close_basis="Angel close", net_change=gain / 10.0, gain_percent=gain,
            volume=volume, oi=oi, bid=bid, ask=ask, future_ltp=100.0,
            exchange_time="2026-09-25 10:15:00",
        )

    quotes = [
        q("TESTCE1", "CE", 120.0, 9.9, 10.1),
        q("TESTCE2", "CE", 90.0, 9.9, 10.1),
        q("TESTCE3", "CE", 80.0, 9.9, 10.1),
        q("TESTCE4", "CE", 70.0, 9.9, 10.1),
        q("TESTPE1", "PE", 150.0, 9.9, 10.1),
        q("TESTPE2", "PE", 110.0, 9.9, 10.1),
        q("TESTPE3", "PE", 100.0, 9.9, 10.1),
        q("TESTPE4", "PE", 90.0, 9.9, 10.1),
        q("TESTBAD", "CE", 999.0, 8.0, 10.0),  # 20% spread -> excluded
    ]
    ce = select_ranked_by_side(quotes, "CE", 5)
    pe = select_ranked_by_side(quotes, "PE", 5)
    assert [x.contract for x in ce[:3]] == ["TESTCE1", "TESTCE2", "TESTCE3"]
    assert [x.contract for x in pe[:3]] == ["TESTPE1", "TESTPE2", "TESTPE3"]
    assert "TESTBAD" not in [x.contract for x in ce]
    ranks = top_ce_pe_ranks(quotes)
    assert len(ranks["CE"]["top1"]) == 1
    assert len(ranks["CE"]["top3"]) == 3
    assert len(ranks["CE"]["top5"]) == 4
    assert len(ranks["PE"]["top5"]) == 4

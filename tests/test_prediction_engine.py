import pytest
import math
from angel_prediction_engine import (
    black76_price,
    calculate_greeks,
    solve_implied_volatility,
    analyze_headline,
    compute_prediction_and_rating
)

def test_black76_pricing():
    # Spot=25000, Strike=25000, T=4/365, r=0.065, sigma=0.15
    T = 4.0 / 365.0
    call_p = black76_price(25000.0, 25000.0, T, 0.065, 0.15, is_call=True)
    put_p = black76_price(25000.0, 25000.0, T, 0.065, 0.15, is_call=False)
    assert call_p > 0
    assert put_p > 0
    # Put-Call parity on futures: C - P = e^(-rT) * (F - K) = 0 when F=K
    diff = abs(call_p - put_p)
    assert diff < 0.01

def test_iv_solver():
    T = 5.0 / 365.0
    target_iv = 0.22 # 22%
    mkt_price = black76_price(25000.0, 25000.0, T, 0.065, target_iv, is_call=True)
    computed_iv = solve_implied_volatility(mkt_price, 25000.0, 25000.0, T, 0.065, is_call=True)
    assert abs(computed_iv - 22.0) <= 0.2

def test_greeks_signs_and_bounds():
    T = 10.0 / 365.0
    greeks_ce = calculate_greeks(25000.0, 25000.0, T, 0.065, 0.20, is_call=True)
    greeks_pe = calculate_greeks(25000.0, 25000.0, T, 0.065, 0.20, is_call=False)

    assert 0.40 <= greeks_ce["delta"] <= 0.60
    assert -0.60 <= greeks_pe["delta"] <= -0.40
    assert greeks_ce["gamma"] > 0
    assert greeks_ce["theta"] < 0
    assert greeks_ce["vega"] > 0

def test_sentiment_and_categorization():
    title_win = "Larsen & Toubro bags mega Rs 5,000 crore contract order win"
    score, cat, impact = analyze_headline(title_win)
    assert score > 0
    assert cat == "ORDER_WIN"
    assert "BULLISH" in impact

    title_probe = "SEBI penalty and CBI probe launched into company accounting fraud"
    score, cat, impact = analyze_headline(title_probe)
    assert score < 0
    assert cat == "REGULATORY_PROBE"
    assert "BEARISH" in impact

def test_prediction_and_intensity_rating():
    # Bullish scenario
    pred_bullish = compute_prediction_and_rating(
        sym="RELIANCE", fut_ltp=2950.0, fut_pct=1.8, fut_obi=0.45,
        ce_ltp=45.0, ce_pct=25.0, ce_oi=2000000, ce_obi=0.30, ce_spread=0.2,
        ce_iv=18.0, ce_delta=0.55, ce_gamma=0.002, ce_theta=-6.0, ce_vega=5.0,
        pe_ltp=15.0, pe_pct=-30.0, pe_oi=1200000, pe_obi=-0.20, pe_spread=0.2,
        pe_iv=19.0, pe_delta=-0.45, pe_gamma=0.002, pe_theta=-5.5, pe_vega=4.8,
        atm_pcr=1.35, max_pain=2940.0, prev_ce_oi=1800000, prev_pe_oi=1200000,
        news_sentiment=0.65, news_category="ORDER_WIN", news_impact="CRITICAL_BULLISH"
    )

    assert pred_bullish["ce_win_prob"] > 70.0
    assert pred_bullish["directional_bias"] == "CALL (CE) BULLISH"
    assert pred_bullish["intensity_score"] >= 65
    assert "CE" in pred_bullish["action_rating"]

    # Bearish scenario
    pred_bearish = compute_prediction_and_rating(
        sym="INFY", fut_ltp=1700.0, fut_pct=-2.2, fut_obi=-0.50,
        ce_ltp=12.0, ce_pct=-40.0, ce_oi=1500000, ce_obi=-0.30, ce_spread=0.2,
        ce_iv=22.0, ce_delta=0.42, ce_gamma=0.0018, ce_theta=-5.0, ce_vega=4.5,
        pe_ltp=55.0, pe_pct=45.0, pe_oi=2500000, pe_obi=0.35, pe_spread=0.2,
        pe_iv=24.0, pe_delta=-0.58, pe_gamma=0.0018, pe_theta=-6.0, pe_vega=4.9,
        atm_pcr=0.60, max_pain=1720.0, prev_ce_oi=1500000, prev_pe_oi=2100000,
        news_sentiment=-0.70, news_category="REGULATORY_PROBE", news_impact="CRITICAL_BEARISH"
    )

    assert pred_bearish["pe_win_prob"] > 70.0
    assert pred_bearish["directional_bias"] == "PUT (PE) BEARISH"
    assert pred_bearish["intensity_score"] >= 65
    assert "PE" in pred_bearish["action_rating"]

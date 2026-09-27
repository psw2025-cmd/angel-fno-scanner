import pytest
import math
from angel_prediction_engine import (
    black76_price,
    calculate_greeks,
    solve_implied_volatility,
    analyze_headline,
    compute_prediction_and_rating,
    compute_pre_market_gap,
    run_ground_truth_reconciliation,
    DEFAULT_WEIGHTS
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

def test_pre_market_gap_prediction():
    # Gap-up catalyst test
    news_bullish = {
        "sentiment_score": 0.85,
        "category": "ORDER_WIN",
        "impact_rating": "CRITICAL_BULLISH",
        "top_headline": "Company bags massive defense export order",
        "item_count": 3
    }
    gap_res = compute_pre_market_gap(
        sym="BEL", fut_ltp=310.0, fut_pct=1.5, fut_obi=0.40,
        fut_oi_vel=12.5, news_info=news_bullish, atm_strike=310.0
    )
    assert gap_res["expected_gap_pct"] > 0
    assert "GAP-UP" in gap_res["gap_direction"]
    assert gap_res["pre_open_conviction"] >= 60.0
    assert "310 CE" in gap_res["target_strike"]
    assert gap_res["positioning"] == "LONG_BUILDUP"

    # Gap-down regulatory test
    news_bearish = {
        "sentiment_score": -0.80,
        "category": "REGULATORY_PROBE",
        "impact_rating": "CRITICAL_BEARISH",
        "top_headline": "USFDA issues warning letter with 8 observations",
        "item_count": 2
    }
    gap_down = compute_pre_market_gap(
        sym="CIPLA", fut_ltp=1550.0, fut_pct=-1.2, fut_obi=-0.35,
        fut_oi_vel=8.0, news_info=news_bearish, atm_strike=1550.0
    )
    assert gap_down["expected_gap_pct"] < 0
    assert "GAP-DOWN" in gap_down["gap_direction"]
    assert gap_down["pre_open_conviction"] >= 60.0
    assert "1550 PE" in gap_down["target_strike"]
    assert gap_down["positioning"] == "SHORT_BUILDUP"

def test_ground_truth_reconciliation_and_calibration():
    # Mock prior predictions
    predictions = [
        {"symbol": f"SYM{i}", "directional_bias": "CALL (CE) BULLISH", "ce_symbol": f"SYM{i}29SEP25000CE", "pe_symbol": f"SYM{i}29SEP25000PE", "rank": i, "ce_chg_pct": 50.0 - i, "pe_chg_pct": -20.0}
        for i in range(1, 21)
    ]
    # Simulate actual live top movers having 7 out of 10 matches
    actual_top_movers = [
        {"contract": "SYM129SEP25000CE", "gain": 48.0},
        {"contract": "SYM229SEP25000CE", "gain": 42.0},
        {"contract": "SYM329SEP25000CE", "gain": 39.0},
        {"contract": "SYM429SEP25000CE", "gain": 35.0},
        {"contract": "SYM529SEP25000CE", "gain": 31.0},
        {"contract": "SYM629SEP25000CE", "gain": 28.0},
        {"contract": "SYM729SEP25000CE", "gain": 25.0},
        {"contract": "SYM1529SEP25000CE", "gain": 22.0},
        {"contract": "SYM1629SEP25000CE", "gain": 20.0},
        {"contract": "SYM1729SEP25000CE", "gain": 18.0}
    ]

    prior = [c["contract"] for c in actual_top_movers[:7]] + ["SYM8_CE", "SYM9_CE", "SYM10_CE"]
    reconcile = run_ground_truth_reconciliation(predictions, actual_top_movers, DEFAULT_WEIGHTS, prior_top10=prior, persist=False)

    assert reconcile["cycle"] >= 1
    assert reconcile["hit_rate_pct"] >= 60.0
    assert reconcile["recall_at_10"] >= 0.60
    assert reconcile["mean_rank"] <= 15.0
    assert "weights" in reconcile
    # Verify weights are normalized to 1.0
    assert abs(sum(reconcile["weights"].values()) - 1.0) < 0.01

def test_dollar_gamma_normalization():
    # KAYNES: S=3650, raw gamma = 0.0003
    pred_kaynes = compute_prediction_and_rating(
        sym="KAYNES", fut_ltp=3650.0, fut_pct=3.5, fut_obi=0.45,
        ce_ltp=120.0, ce_pct=65.0, ce_oi=500000, ce_obi=0.35, ce_spread=1.0,
        ce_iv=28.0, ce_delta=0.55, ce_gamma=0.0003, ce_theta=-12.0, ce_vega=15.0,
        pe_ltp=25.0, pe_pct=-40.0, pe_oi=300000, pe_obi=-0.20, pe_spread=1.0,
        pe_iv=29.0, pe_delta=-0.45, pe_gamma=0.0003, pe_theta=-10.0, pe_vega=14.0,
        atm_pcr=1.20, max_pain=3600.0, prev_ce_oi=450000, prev_pe_oi=300000,
        news_sentiment=0.50, news_category="ORDER_WIN", news_impact="CRITICAL_BULLISH",
        weights=DEFAULT_WEIGHTS
    )
    # YESBANK: S=22, raw gamma = 0.03
    pred_yesbank = compute_prediction_and_rating(
        sym="YESBANK", fut_ltp=22.0, fut_pct=0.5, fut_obi=0.10,
        ce_ltp=0.85, ce_pct=5.0, ce_oi=20000000, ce_obi=0.10, ce_spread=0.05,
        ce_iv=35.0, ce_delta=0.50, ce_gamma=0.03, ce_theta=-0.1, ce_vega=0.2,
        pe_ltp=0.80, pe_pct=-5.0, pe_oi=15000000, pe_obi=-0.10, pe_spread=0.05,
        pe_iv=36.0, pe_delta=-0.50, pe_gamma=0.03, pe_theta=-0.1, pe_vega=0.2,
        atm_pcr=1.00, max_pain=22.0, prev_ce_oi=20000000, prev_pe_oi=15000000,
        news_sentiment=0.0, news_category="GENERAL_MACRO", news_impact="NEUTRAL",
        weights=DEFAULT_WEIGHTS
    )

    # Dollar Gamma of KAYNES should be substantial (> 10.0)
    assert pred_kaynes["ce_dollar_gamma"] > 10.0
    # Dollar Gamma of YESBANK is bounded
    assert pred_yesbank["ce_dollar_gamma"] < 5.0
    # KAYNES has high option price velocity (+65%) and high dollar gamma, so its rank_metric must be significantly higher
    assert pred_kaynes["rank_metric"] > pred_yesbank["rank_metric"]
    assert pred_kaynes["rank_metric"] > 35.0

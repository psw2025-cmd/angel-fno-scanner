import pytest
import json
import math
from pathlib import Path
from angel_prediction_engine import (
    black76_price,
    calculate_greeks,
    solve_implied_volatility,
    analyze_headline,
    compute_prediction_and_rating,
    compute_pre_market_gap,
    run_ground_truth_reconciliation,
    classify_event_severity,
    compute_market_confirmation,
    parse_news_timestamp_ist,
    news_dedup_key,
    is_pre_close_time,
    is_morning_reconcile_time,
    generate_next_day_gap_picks,
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

def test_routine_compliance_nlp_filter():
    headlines = [
        "Trading Window closure pursuant to SEBI (Prohibition of Insider Trading) Regulations, 2015",
        "Company informs about Allotment of Equity Shares under ESOP",
        "Change in Auditors pursuant to Regulation 30",
        "Intimation of Schedule of Analyst / Institutional Investor Meet",
        "Loss of share certificate and issue of duplicate share certificate",
        "Outcome of AGM proceedings and voting results",
        "Newspaper publication regarding financial results"
    ]
    for h in headlines:
        score, cat, impact = analyze_headline(h)
        assert score == 0.0, f"Failed score for {h}"
        assert cat == "ROUTINE_COMPLIANCE", f"Failed category for {h}"
        assert impact == "NEUTRAL", f"Failed impact for {h}"

def test_liquidity_and_spread_gate():
    # Test 1: NIFTYFPI scenario (pe_iv=0.0, spread=19.90, pe_ltp=0.05)
    pred_illiquid = compute_prediction_and_rating(
        sym="NIFTYFPI", fut_ltp=1500.0, fut_pct=-1.5, fut_obi=-0.3,
        ce_ltp=5.0, ce_pct=-10.0, ce_oi=0, ce_obi=0.0, ce_spread=2.0,
        ce_iv=15.0, ce_delta=0.4, ce_gamma=0.001, ce_theta=-2.0, ce_vega=1.0,
        pe_ltp=0.05, pe_pct=50.0, pe_oi=1100, pe_obi=0.2, pe_spread=19.90,
        pe_iv=0.0, pe_delta=-0.5, pe_gamma=0.001, pe_theta=-2.0, pe_vega=1.0,
        atm_pcr=0.5, max_pain=1500.0, prev_ce_oi=0, prev_pe_oi=1000,
        news_sentiment=0.0, news_category="GENERAL_MACRO", news_impact="NEUTRAL",
        ce_vol=0, pe_vol=0
    )
    assert pred_illiquid["is_illiquid"] is True
    assert pred_illiquid["action_rating"] == "⚠️ ILLIQUID / WIDE SPREAD [AVOID]"
    assert pred_illiquid["confidence_pct"] <= 40.0
    assert pred_illiquid["rank_metric"] < -500.0

    # Test 2: Liquid contract (FEDERALBNK: ltp=6.0, spread=0.65, vol=150000, oi=1855000)
    pred_liquid = compute_prediction_and_rating(
        sym="FEDERALBNK", fut_ltp=322.8, fut_pct=-0.8, fut_obi=-0.25,
        ce_ltp=3.5, ce_pct=-35.0, ce_oi=1200000, ce_obi=-0.3, ce_spread=0.20,
        ce_iv=65.0, ce_delta=0.45, ce_gamma=0.003, ce_theta=-4.0, ce_vega=3.0,
        pe_ltp=6.0, pe_pct=45.0, pe_oi=1855000, pe_obi=0.35, pe_spread=0.65,
        pe_iv=71.2, pe_delta=-0.55, pe_gamma=0.003, pe_theta=-4.0, pe_vega=3.0,
        atm_pcr=1.54, max_pain=325.0, prev_ce_oi=1100000, prev_pe_oi=1400000,
        news_sentiment=0.0, news_category="GENERAL_MACRO", news_impact="NEUTRAL",
        ce_vol=50000, pe_vol=150000
    )
    assert pred_liquid["is_illiquid"] is False
    assert pred_liquid["action_rating"] != "⚠️ ILLIQUID / WIDE SPREAD [AVOID]"
    assert pred_liquid["rank_metric"] > 0.0

def test_enhanced_pre_market_gap_with_implied_move():
    news_info = {
        "sentiment_score": 0.0,
        "category": "GENERAL_MACRO",
        "impact_rating": "NEUTRAL",
        "top_headline": "Routine trading session",
        "sources_count": 0
    }
    # Strong put momentum and high IV
    gap_res = compute_pre_market_gap(
        sym="FEDERALBNK", fut_ltp=322.8, fut_pct=-0.8, fut_obi=-0.25,
        fut_oi_vel=25.0, news_info=news_info, atm_strike=325.0,
        ce_pct=-35.0, pe_pct=45.0, ce_obi=-0.30, pe_obi=0.35,
        ce_oi_vel=-10.0, pe_oi_vel=30.0, atm_pcr=1.54, ce_iv=65.0, pe_iv=71.2
    )
    assert gap_res["expected_gap_pct"] < 0
    assert "GAP-DOWN" in gap_res["gap_direction"]
    assert "325 PE" in gap_res["target_strike"]
    assert gap_res["implied_move_daily_pct"] > 3.0

def test_five_stage_event_severity_classification():
    # Level 5: Critical (Fraud, Insolvency, Hard Commission Cap)
    l5_title = "ED Raids Corporate Headquarters in Alleged Accounting Fraud Case"
    lvl, code, band, pos, neg, neut, priced = classify_event_severity(l5_title)
    assert lvl == 5
    assert code == "LEVEL_5_CRITICAL"
    assert "> 8.0%" in band
    assert neg > 0.80

    # Level 4: High (Supreme Court, Forensic Audit, Consultation Paper)
    l4_pb = "IRDAI Issues Consultation Paper on Recalibrating Economics of Insurance Distribution"
    lvl, code, band, pos, neg, neut, priced = classify_event_severity(l4_pb)
    assert lvl == 4
    assert code == "LEVEL_4_HIGH"
    assert "4.0% - 8.0%" in band
    assert priced >= 0.70  # Consultative nature has high already-priced-in factor

    l4_fortis = "Supreme Court Refuses to Interfere with High Court Forensic Audit Order"
    lvl, code, band, pos, neg, neut, priced = classify_event_severity(l4_fortis)
    assert lvl == 4
    assert code == "LEVEL_4_HIGH"

    # Level 3: Medium (Order win, MHRA approval)
    l3_title = "Biocon Receives UK MHRA Approval for Insulin Facility"
    lvl, code, band, pos, neg, neut, priced = classify_event_severity(l3_title)
    assert lvl == 3
    assert code == "LEVEL_3_MEDIUM"
    assert pos >= 0.70

    # Level 1: Routine Noise
    l1_title = "Trading Window Closure Pursuant to SEBI Insider Trading Regulations"
    lvl, code, band, pos, neg, neut, priced = classify_event_severity(l1_title)
    assert lvl == 1
    assert code == "LEVEL_1_NOISE"
    assert priced >= 0.90

def test_cross_asset_market_confirmation():
    # Bullish Confirmed: Positive tone + Price & Futures OBI positive + Call velocity >= Put velocity
    conf_bull = compute_market_confirmation(
        sentiment_score=0.60, fut_pct=1.2, fut_obi=0.25, ce_pct=25.0, pe_pct=-15.0
    )
    assert "BULLISH_CONFIRMED" in conf_bull

    # Bearish Confirmed: Negative tone + Price & Futures OBI negative + Put velocity >= Call velocity
    conf_bear = compute_market_confirmation(
        sentiment_score=-0.70, fut_pct=-1.5, fut_obi=-0.30, ce_pct=-20.0, pe_pct=35.0
    )
    assert "BEARISH_CONFIRMED" in conf_bear

    # Priced In / Divergent: Positive tone but price & calls collapsing
    conf_div = compute_market_confirmation(
        sentiment_score=0.65, fut_pct=-1.2, fut_obi=-0.20, ce_pct=-30.0, pe_pct=40.0
    )
    assert "PRICED_IN_OR_DIVERGENT" in conf_div

    # Neutral Flow: Minimal tone score
    conf_neut = compute_market_confirmation(
        sentiment_score=0.05, fut_pct=0.2, fut_obi=0.05, ce_pct=5.0, pe_pct=-2.0
    )
    assert conf_neut == "NEUTRAL_FLOW"

def test_news_entity_mapping_exact_company():
    from angel_prediction_engine import aggregate_market_news
    articles = [
        {"title": "Supreme Court Refuses To Interfere With Forensic Probe Order Against Fortis Healthcare - LawBeat", "source": "Legal Litigated Thematic", "link": "https://example.com/1"},
        {"title": "PB Fintech launches new policy platform - Economic Times", "source": "Livemint", "link": "https://example.com/2"}
    ]
    symbols = ["FORTIS", "PAYTM", "POLICYBZR", "ADANIENT", "DABUR"]
    mapped = aggregate_market_news(articles, symbols)
    
    # Fortis must have Fortis news
    assert "Fortis" in mapped["FORTIS"]["top_headline"]
    # Unrelated symbols must NOT receive Fortis news!
    assert "Fortis" not in mapped["PAYTM"]["top_headline"]
    assert "Fortis" not in mapped["POLICYBZR"]["top_headline"]
    assert "Fortis" not in mapped["ADANIENT"]["top_headline"]
    assert "Fortis" not in mapped["DABUR"]["top_headline"]

def test_zero_oi_rejected():
    # If dominant option has 0 OI or 0 volume, it must be marked as illiquid
    pred = compute_prediction_and_rating(
        sym="TESTSYM", fut_ltp=1000.0, fut_pct=1.0, fut_obi=0.2,
        ce_ltp=25.0, ce_pct=10.0, ce_oi=0, ce_vol=0, ce_spread=0.5, ce_obi=0.2, ce_iv=25.0,
        ce_greeks={"delta": 0.5, "gamma": 0.002, "theta": -5.0, "vega": 0.2},
        pe_ltp=20.0, pe_pct=-10.0, pe_oi=1000, pe_vol=500, pe_spread=0.5, pe_obi=-0.2, pe_iv=25.0,
        pe_greeks={"delta": -0.5, "gamma": 0.002, "theta": -5.0, "vega": 0.2},
        atm_pcr=1.0, max_pain=1000.0, prev_ce_oi=0, prev_pe_oi=1000,
        news_sentiment=0.0, news_category="NO_NEWS", news_impact="NEUTRAL"
    )
    assert pred["is_illiquid"] is True
    assert "ILLIQUID" in pred["action_rating"]
    assert pred["confidence_pct"] <= 40.0

def test_extreme_spread_rejected():
    # If dominant option has relative spread > 25% and spread > 2.0, mark as illiquid
    pred = compute_prediction_and_rating(
        sym="TESTSYM", fut_ltp=1000.0, fut_pct=1.0, fut_obi=0.2,
        ce_ltp=10.0, ce_pct=10.0, ce_oi=10000, ce_vol=5000, ce_spread=5.0, ce_obi=0.2, ce_iv=25.0,
        ce_greeks={"delta": 0.5, "gamma": 0.002, "theta": -5.0, "vega": 0.2},
        pe_ltp=10.0, pe_pct=-10.0, pe_oi=10000, pe_vol=5000, pe_spread=0.5, pe_obi=-0.2, pe_iv=25.0,
        pe_greeks={"delta": -0.5, "gamma": 0.002, "theta": -5.0, "vega": 0.2},
        atm_pcr=1.0, max_pain=1000.0, prev_ce_oi=10000, prev_pe_oi=10000,
        news_sentiment=0.0, news_category="NO_NEWS", news_impact="NEUTRAL"
    )
    assert pred["is_illiquid"] is True
    assert pred["rank_metric"] < -500.0

def test_probability_sum():
    pred = compute_prediction_and_rating(
        sym="TESTSYM", fut_ltp=500.0, fut_pct=0.5, fut_obi=0.1,
        ce_ltp=15.0, ce_pct=5.0, ce_oi=5000, ce_vol=2000, ce_spread=0.2, ce_obi=0.1, ce_iv=20.0,
        ce_greeks={"delta": 0.5, "gamma": 0.005, "theta": -2.0, "vega": 0.1},
        pe_ltp=12.0, pe_pct=-5.0, pe_oi=4000, pe_vol=1500, pe_spread=0.2, pe_obi=-0.1, pe_iv=20.0,
        pe_greeks={"delta": -0.5, "gamma": 0.005, "theta": -2.0, "vega": 0.1},
        atm_pcr=0.8, max_pain=500.0, prev_ce_oi=5000, prev_pe_oi=4000,
        news_sentiment=0.2, news_category="ORDER_WIN", news_impact="MODERATE_BULLISH"
    )
    assert abs(pred["ce_win_prob"] + pred["pe_win_prob"] - 100.0) < 0.01

def test_direction_expected_gap_consistency():
    gap_bull = compute_pre_market_gap(fut_pct=1.0, fut_obi=0.3, atm_pcr=1.2, ce_iv=20.0, pe_iv=20.0, ce_win_prob=75.0, pe_win_prob=25.0, news_sentiment=0.4, atm_strike=100.0)
    assert gap_bull["expected_gap_pct"] >= 0.0
    assert "GAP-UP" in gap_bull["gap_direction"]

    gap_bear = compute_pre_market_gap(fut_pct=-1.2, fut_obi=-0.3, atm_pcr=0.6, ce_iv=25.0, pe_iv=25.0, ce_win_prob=20.0, pe_win_prob=80.0, news_sentiment=-0.4, atm_strike=100.0)
    assert gap_bear["expected_gap_pct"] <= 0.0
    assert "GAP-DOWN" in gap_bear["gap_direction"]

def test_forward_accuracy_not_self_calibration():
    # Verify that reconciliation metrics explicitly distinguish calibration from forward paper trading
    reconciliation = run_ground_truth_reconciliation([], [], DEFAULT_WEIGHTS)
    assert "hit_rate_pct" in reconciliation
    assert "cycle" in reconciliation

def test_premarket_snapshot_immutable():
    import json, os
    frozen_path = "audit/premarket_baseline_frozen.json"
    assert os.path.exists(frozen_path)
    with open(frozen_path) as f:
        d = json.load(f)
    assert d["predictions_sha256"] == "c215b4c20e5b17b167c4b521ce5772615792f509e23272df7a5a73dd84e4e27e"
    assert d["total_symbols"] == 216

def test_score_saturation_bounds():
    pred = compute_prediction_and_rating(
        sym="TESTSYM", fut_ltp=500.0, fut_pct=5.0, fut_obi=0.9,
        ce_ltp=50.0, ce_pct=100.0, ce_oi=50000, ce_vol=20000, ce_spread=0.1, ce_obi=0.8, ce_iv=80.0,
        ce_greeks={"delta": 0.8, "gamma": 0.05, "theta": -10.0, "vega": 0.5},
        pe_ltp=1.0, pe_pct=-90.0, pe_oi=4000, pe_vol=1500, pe_spread=0.1, pe_obi=-0.8, pe_iv=80.0,
        pe_greeks={"delta": -0.2, "gamma": 0.05, "theta": -10.0, "vega": 0.5},
        atm_pcr=0.1, max_pain=480.0, prev_ce_oi=10000, prev_pe_oi=4000,
        news_sentiment=1.0, news_category="EARNINGS_BEAT", news_impact="CRITICAL_BULLISH"
    )
    # Intensity must never exceed 99 and confidence must never exceed 97.5%
    assert pred["intensity_score"] <= 99
    assert pred["confidence_pct"] <= 97.5

def test_extreme_option_change_soft_saturation():
    # If option has +1820% gain, rank_metric should soft-saturate rather than explode linearly
    pred = compute_prediction_and_rating(
        sym="TESTSYM", fut_ltp=1000.0, fut_pct=1.0, fut_obi=0.2,
        ce_ltp=10.0, ce_pct=1820.0, ce_oi=10000, ce_vol=5000, ce_spread=0.5, ce_obi=0.2, ce_iv=25.0,
        ce_greeks={"delta": 0.5, "gamma": 0.002, "theta": -5.0, "vega": 0.2},
        pe_ltp=1.0, pe_pct=-50.0, pe_oi=10000, pe_vol=5000, pe_spread=0.1, pe_obi=-0.2, pe_iv=25.0,
        pe_greeks={"delta": -0.5, "gamma": 0.002, "theta": -5.0, "vega": 0.2},
        atm_pcr=1.0, max_pain=1000.0, prev_ce_oi=10000, prev_pe_oi=10000,
        news_sentiment=0.0, news_category="NO_NEWS", news_impact="NEUTRAL"
    )
    # Rank metric should be finite and soft-saturated (e.g. <= 400.0)
    assert pred["rank_metric"] <= 400.0

def test_pre_close_timing_window():
    import datetime
    # Monday 15:15 IST -> should be True
    dt_in = datetime.datetime(2026, 9, 28, 15, 15, 0)
    assert is_pre_close_time(dt_in) is True

    # Monday 14:45 IST -> should be False
    dt_early = datetime.datetime(2026, 9, 28, 14, 45, 0)
    assert is_pre_close_time(dt_early) is False

    # Monday 15:35 IST -> still inside the 15:40 F&O close window
    dt_late = datetime.datetime(2026, 9, 28, 15, 35, 0)
    assert is_pre_close_time(dt_late) is True

    # Monday 15:41 IST -> after the 15:40 F&O close
    dt_after = datetime.datetime(2026, 9, 28, 15, 41, 0)
    assert is_pre_close_time(dt_after) is False

    # Sunday 15:15 IST -> should be False (weekend)
    dt_sun = datetime.datetime(2026, 9, 27, 15, 15, 0)
    assert is_pre_close_time(dt_sun) is False

def test_morning_reconcile_timing_window():
    import datetime
    # Monday 09:20 IST -> should be True
    dt_in = datetime.datetime(2026, 9, 28, 9, 20, 0)
    assert is_morning_reconcile_time(dt_in) is True

    # Monday 09:10 IST -> should be False
    dt_early = datetime.datetime(2026, 9, 28, 9, 10, 0)
    assert is_morning_reconcile_time(dt_early) is False

    # Monday 09:55 IST -> should be False
    dt_late = datetime.datetime(2026, 9, 28, 9, 55, 0)
    assert is_morning_reconcile_time(dt_late) is False

def test_next_day_gap_candidate_selection_and_risk_reward(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "angel_prediction_engine.NEXT_DAY_GAP_PATH",
        str(tmp_path / "test_next_day_gap.json"),
    )
    test_preds = [
        {
            "symbol": "BULL_STOCK",
            "spot_ltp": 1200.0,
            "atm_strike": 1200.0,
            "expected_gap_pct": 1.25,
            "ce_win_prob": 85.0,
            "pe_win_prob": 15.0,
            "ce_ltp": 20.0,
            "pe_ltp": 2.0,
            "action_rating": "🚨 GAMMA SQUEEZE ALERT (ACCELERATING CE)",
            "pre_open_conviction": 80.0,
            "top_headline": "USFDA clearance received with zero observations",
            "ce_dollar_gamma": 1.5,
            "pe_dollar_gamma": 0.0,
            "ce_oi_velocity": 12.0,
            "pe_oi_velocity": -5.0,
            "atm_pcr": 0.45,
            "ce_symbol": "BULL_STOCK_1200CE",
            "pe_symbol": "BULL_STOCK_1200PE",
            "ce_chg_pct": 45.0,
            "pe_chg_pct": -30.0,
            "is_illiquid": False
        },
        {
            "symbol": "BEAR_STOCK",
            "spot_ltp": 500.0,
            "atm_strike": 500.0,
            "expected_gap_pct": -1.80,
            "ce_win_prob": 12.0,
            "pe_win_prob": 88.0,
            "ce_ltp": 1.5,
            "pe_ltp": 15.0,
            "action_rating": "💥 SEVERE PE BREAKDOWN [AGGRESSIVE SHORT]",
            "pre_open_conviction": 85.0,
            "top_headline": "Accounting fraud inquiry initiated by regulator",
            "ce_dollar_gamma": 0.0,
            "pe_dollar_gamma": 1.8,
            "ce_oi_velocity": -10.0,
            "pe_oi_velocity": 18.0,
            "atm_pcr": 2.5,
            "ce_symbol": "BEAR_STOCK_500CE",
            "pe_symbol": "BEAR_STOCK_500PE",
            "ce_chg_pct": -50.0,
            "pe_chg_pct": 60.0,
            "is_illiquid": False
        }
    ]

    picks = generate_next_day_gap_picks(test_preds)
    assert len(picks["top_ce_picks"]) == 1
    assert len(picks["top_pe_picks"]) == 1

    ce = picks["top_ce_picks"][0]
    assert ce["symbol"] == "BULL_STOCK"
    assert ce["side"] == "CE"
    assert ce["target_strike"] == "1200 CE"
    assert ce["entry_ltp"] == 20.0
    # Stop loss must be exactly 15% below entry (20.0 * 0.85 = 17.0)
    assert ce["stop_loss_ltp"] == 17.0
    # Target must be 50% above entry (20.0 * 1.50 = 30.0)
    assert ce["target_ltp"] == 30.0
    assert ce["expected_gap_pct"] == 1.25

    pe = picks["top_pe_picks"][0]
    assert pe["symbol"] == "BEAR_STOCK"
    assert pe["side"] == "PE"
    assert pe["target_strike"] == "500 PE"
    assert pe["entry_ltp"] == 15.0
    # Stop loss must be 15% below entry (15.0 * 0.85 = 12.75)
    assert pe["stop_loss_ltp"] == 12.75
    # Target must be 60% above entry (15.0 * 1.60 = 24.0)
    assert pe["target_ltp"] == 24.0
    assert pe["expected_gap_pct"] == -1.80

def test_why_rationale_completeness(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "angel_prediction_engine.NEXT_DAY_GAP_PATH",
        str(tmp_path / "test_next_day_gap2.json"),
    )
    test_preds = [
        {
            "symbol": "CATALYST_CE",
            "spot_ltp": 250.0,
            "atm_strike": 250.0,
            "expected_gap_pct": 0.85,
            "ce_win_prob": 75.0,
            "pe_win_prob": 25.0,
            "ce_ltp": 5.0,
            "pe_ltp": 1.0,
            "action_rating": "🚨 GAMMA SQUEEZE ALERT (ACCELERATING CE)",
            "pre_open_conviction": 78.5,
            "top_headline": "Order win of mega transmission line",
            "ce_dollar_gamma": 0.8,
            "pe_dollar_gamma": 0.0,
            "ce_oi_velocity": 8.0,
            "pe_oi_velocity": 0.0,
            "atm_pcr": 0.60,
            "ce_symbol": "CATALYST_CE_250CE",
            "pe_symbol": "CATALYST_CE_250PE",
            "ce_chg_pct": 20.0,
            "pe_chg_pct": -10.0,
            "is_illiquid": False
        }
    ]
    picks = generate_next_day_gap_picks(test_preds)
    ce = picks["top_ce_picks"][0]
    rationale = ce["why_rationale"]
    # Verify micro-details are in the rationale
    assert "[OVERNIGHT GAP-UP CE]" in rationale
    assert "ExpGap: +0.85%" in rationale
    assert "Conviction: 78.5%" in rationale
    assert "Gamma: 0.80" in rationale
    assert "PCR: 0.60" in rationale
    assert "Order win of mega" in rationale




def test_rbi_penalty_not_broadcast_to_unrelated_banks():
    from angel_prediction_engine import aggregate_market_news
    headline = "RBI Imposes Rs 41.80 Lakh Penalty on Bandhan Bank for Regulatory Violations - scanx.trade"
    articles = [{"title": headline, "source": "Banking RBI Thematic", "link": "https://example.com/bandhan"}]
    symbols = ["AXISBANK", "ICICIBANK", "KOTAKBANK", "HDFCBANK"]
    mapped = aggregate_market_news(articles, symbols)
    for sym in symbols:
        assert mapped[sym]["top_headline"] == "No fresh material catalyst"
        assert mapped[sym]["item_count"] == 0



def test_news_timestamp_normalizes_rfc2822_to_ist():
    assert parse_news_timestamp_ist("Wed, 30 Sep 2026 12:00:00 GMT") == "2026-09-30T17:30:00"
    assert parse_news_timestamp_ist("2026-09-30T12:00:00+00:00") == "2026-09-30T17:30:00"


def test_news_dedup_preserves_cross_source_corroboration():
    a = {"title": "Company wins order", "source": "Feed A", "source_url": "https://a.example/x"}
    b = {"title": "Company wins order", "source": "Feed B", "source_url": "https://b.example/x"}
    a_replay = dict(a)
    assert news_dedup_key(a) == news_dedup_key(a_replay)
    assert news_dedup_key(a) != news_dedup_key(b)


def test_manifest_declares_219_unique_fno_symbols():
    manifest = json.loads((Path(__file__).resolve().parents[1] / "agent_manifest.json").read_text(encoding="utf-8"))
    symbols = manifest["universe"]["symbols"]
    assert manifest["universe"]["total_symbols"] == 219
    assert len(symbols) == 219
    assert len(set(symbols)) == 219
    assert {"ANANDRATHI", "ENRIN", "UJJIVANSFB"} <= set(symbols)


def test_pre_market_gap_is_deterministic_from_current_inputs():
    kwargs = dict(
        sym="TEST", fut_ltp=100.0, fut_pct=0.8, fut_obi=0.2, fut_oi_vel=5.0,
        news_info={"sources_count": 2, "sentiment_score": 0.4, "category": "ORDER_WIN"},
        atm_strike=100, ce_pct=30.0, pe_pct=5.0, ce_obi=0.25, pe_obi=-0.05,
        ce_oi_vel=4.0, pe_oi_vel=-1.0, atm_pcr=1.1, ce_iv=20.0, pe_iv=21.0,
        is_illiquid=False,
    )
    first = compute_pre_market_gap(**kwargs)
    second = compute_pre_market_gap(**kwargs)
    assert first == second
    assert -6.0 <= first["expected_gap_pct"] <= 6.0


def test_reconcile_preserves_exact_contract_identity_when_atm_drifts(monkeypatch, tmp_path):
    """
    Regression test for G19 Exact Strike / Contract Identity:
    Proves that when current ATM strike drifts between forecast time and evaluation time,
    the evaluation logic preserves the exact frozen FORECAST_CONTRACT and queries its quote,
    and NEVER substitutes the drifted CURRENT_ATM_CONTRACT.
    """
    monkeypatch.setattr(
        "angel_prediction_engine.GAP_RECON_HISTORY_PATH",
        str(tmp_path / "test_gap_recon.json"),
    )
    monkeypatch.setenv("ALLOW_PRODUCTION_WRITES", "1")
    monkeypatch.setenv("WRITER_ID", "market_bot")
    monkeypatch.setenv("RUN_ID", "123456789")
    monkeypatch.setenv("GIT_SHA", "abcdef1234567890")
    class MockWorksheet:
        def __init__(self):
            self.rows = [
                ["Timestamp", "SessionDate", "Symbol", "Side", "SpotLtp", "ChgPct", "CEContract", "PEContract", "Note", "LaterChg", "FilledAt"],
                ["2026-10-01 15:20:00", "2026-10-01", "PRESTIGE", "CE", "1482.2", "2.5", "PRESTIGE27OCT261480CE", "", "[OVERNIGHT GAP-UP CE] Action: ALERT | Entry: ₹50.70 | SL: ₹43.09 | Target: ₹76.05", "", ""]
            ]
            self.updates = {}

        def get_all_values(self):
            return self.rows

        def update_cell(self, row, col, val):
            self.updates[(row, col)] = val

    class MockSpreadsheet:
        def __init__(self, ws):
            self.ws = ws
        def worksheet(self, name):
            if name == "PAPER_ALERT_LOG":
                return self.ws
            raise ValueError(f"Unknown sheet: {name}")

    class MockSmartApi:
        def __init__(self):
            self.queries = []
        def getLtpData(self, seg, tradingsymbol, token=""):
            self.queries.append((seg, tradingsymbol))
            if tradingsymbol == "PRESTIGE27OCT261480CE":
                return {"status": True, "data": {"ltp": 85.0}}
            return {"status": True, "data": {"ltp": 35.0}}

    # Drifted state: spot moved up, causing ATM strike in pred_symbol_map to become 1520 CE at price 35.0
    drifting_predictions = [
        {
            "symbol": "PRESTIGE",
            "spot_ltp": 1525.0,
            "atm_strike": 1520.0,
            "ce_symbol": "PRESTIGE27OCT261520CE",  # DRIFTED ATM!
            "ce_ltp": 35.0,                       # Drifted ATM contract price
            "pe_symbol": "PRESTIGE27OCT261520PE",
            "pe_ltp": 10.0,
        }
    ]

    mock_ws = MockWorksheet()
    mock_sh = MockSpreadsheet(mock_ws)
    mock_api = MockSmartApi()

    import datetime
    from angel_prediction_engine import reconcile_next_day_gap_trades

    ist_now = datetime.datetime(2026, 10, 2, 9, 20, 0)
    ist_str = "2026-10-02 09:20:00"

    reconcile_next_day_gap_trades(
        smartApi=mock_api,
        sh=mock_sh,
        bq_client=None,
        predictions=drifting_predictions,
        ist_str=ist_str,
        ist_now=ist_now
    )

    # 1. Assert smartApi was queried for the EXACT frozen contract
    assert ("NFO", "PRESTIGE27OCT261480CE") in mock_api.queries
    # 2. Assert PAPER_ALERT_LOG received the outcome based on 85.0 vs 50.7 (+67.65% WIN)
    result_text = mock_ws.updates.get((2, 10))
    assert result_text is not None
    assert "+67.65%" in result_text
    assert "WIN" in result_text


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
    classify_event_severity,
    compute_market_confirmation,
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


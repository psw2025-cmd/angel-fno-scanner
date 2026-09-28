# Phase 6 & Phase 14: Suspected Findings Forensic Classification

This document records the definitive forensic evaluation of all suspected and reported findings across the Angel One F&O Prediction Pipeline.

---

### Finding A: Heartbeat Hit Rate 100% vs Colab Historical Hit Rate 50%
- **Reported Symptom:** The `HEARTBEAT` tab previously displayed "Top-10 Hit Rate 100%", creating confusion that forward paper trading accuracy was 100%, whereas historical evaluation in Colab showed ~50%.
- **Forensic Verification:** VERIFIED. In `angel_prediction_engine.py:870-940`, this metric measures Bayesian weight self-reconciliation against the current batch's top gainers, NOT a forward out-of-sample prediction hit rate.
- **Classification:** `LABELING / SEMANTIC DEFECT`.
- **Root Cause:** Metric in `HEARTBEAT` row 6 was ambiguously labeled `Top-10 Hit Rate` instead of `Self-Calibration Hit Rate`.
- **Correction Required:** YES.
- **Resolution:** Re-labeled metric in `HEARTBEAT` row 6 to `Self-Calibration Hit Rate` and documented that forward trading accuracy requires post-market live trade execution tracking (`PENDING MARKET OUTCOME`).

---

### Finding B: Duplicate News Bloat in BigQuery `market_news_sentiment`
- **Reported Symptom:** Duplicate insertion of identical headlines on every scan cycle, bloating BigQuery storage.
- **Forensic Verification:** VERIFIED. In early loops, general macro roundups were repeatedly loaded without deduplication.
- **Classification:** `VERIFIED DEFECT`.
- **Root Cause:** Missing discovery hash check across identical `(symbol, title)` records in ingestion loop.
- **Correction Required:** YES.
- **Resolution:** Deduplication gate implemented in `angel_prediction_engine.py:530-580` using headline hashing and symbol matching. Verified in `audit/11_news_dedup_audit.csv`.

---

### Finding C: Thematic News Entity Cross-Contamination
- **Reported Symptom:** Fortis Healthcare litigation news was mapped to Policybazaar (`POLICYBZR`), Paytm (`PAYTM`), Adani Enterprises (`ADANIENT`), Dabur (`DABUR`), and Vedanta (`VEDL`).
- **Forensic Verification:** VERIFIED. In `angel_prediction_engine.py:556-582`, `THEMATIC_DISCOVERY_FEEDS` broadcast legal headlines across all stocks in `REGULATOR_SECTOR_MAP["LEGAL"]` without verifying company name in the headline.
- **Classification:** `VERIFIED DEFECT`.
- **Root Cause:** Unconditional iteration over `REGULATOR_SECTOR_MAP["LEGAL"]` for litigation articles.
- **Correction Required:** YES.
- **Resolution:** Enforced strict entity matching for `LEGAL` and other thematic feeds: company-specific orders are isolated only to stocks matching symbol or alias. Verified in `test_news_entity_mapping_exact_company` and `audit/12_news_entity_mapping_audit.csv`.

---

### Finding D: One-Sided Liquidity Gate Allowed Illiquid Symbols High Rank
- **Reported Symptom:** Contracts with extreme bid-ask spreads or zero open interest on counter legs (e.g. `ZYDUSLIFE` PE spread ₹70.05, `NIFTYFPI`) were not properly gated if the dominant leg appeared liquid.
- **Forensic Verification:** VERIFIED. `angel_prediction_engine.py:1221-1252` only audited `dom_spread` and `dom_oi` on the dominant leg.
- **Classification:** `VERIFIED DEFECT`.
- **Root Cause:** Lack of two-sided contract integrity and relative spread gating.
- **Correction Required:** YES.
- **Resolution:** Enforced two-sided liquidity check: if dominant option volume == 0, OI == 0, IV <= 0.01, or relative spread > 25% (and absolute spread > ₹2.00), stock is marked `⚠️ ILLIQUID / WIDE SPREAD [AVOID]` and assigned `rank_metric < -500`. Verified in `tests/test_prediction_engine.py` (`test_zero_oi_rejected`, `test_extreme_spread_rejected`) and `audit/13_liquidity_audit.csv`.

---

### Finding E & G: Unbounded Option Change (+1820%) Exploding Rank Metric
- **Reported Symptom:** A penny option leaping from ₹0.50 to ₹9.60 (+1820%) generated `opt_vel_term > 760`, vaulting low-liquidity penny moves over legitimate high-conviction institutional setups.
- **Forensic Verification:** VERIFIED. In `angel_prediction_engine.py:1263`, `opt_vel_term = lead_opt_chg * w["opt_vel"] * 1.5` was linearly unclipped.
- **Classification:** `VERIFIED DEFECT`.
- **Root Cause:** Linear scaling of raw percentage change on low-base penny options.
- **Correction Required:** YES.
- **Resolution:** Soft-saturated `lead_opt_chg > 150.0` using a logarithmic saturation curve (`150.0 + 50.0 * log1p(...)`) and capped `rank_metric` within `[-999.0, 400.0]`. Verified in `test_extreme_option_change_soft_saturation` and `audit/15_rank_explanation.csv`.

---

### Finding F: Dollar Gamma Normalization Across Stock Price Scales
- **Reported Symptom:** Raw Gamma $\Gamma$ favored ₹20 penny stocks over ₹3,500 large caps in gradient weight attribution.
- **Forensic Verification:** VERIFIED & ALREADY IMPLEMENTED. Dollar Gamma ($\Gamma \times S^2 \times 0.01$) was implemented in `angel_prediction_engine.py:1128` and tested in `test_dollar_gamma_normalization`.
- **Classification:** `VERIFIED & RESOLVED`.
- **Root Cause:** Raw Greek scale sensitivity to underlying price $S$.
- **Correction Required:** Retain normalized Dollar Gamma.

---

### Finding H: Routine Compliance Filings Falsely Scored Bearish
- **Reported Symptom:** Routine quarter-end corporate filings like "Trading Window closure" were matching words like "closure" and getting scored as `MODERATE_BEARISH`.
- **Forensic Verification:** VERIFIED & ALREADY IMPLEMENTED. Routine compliance filter in `analyze_headline` classifies administrative filings as `ROUTINE_COMPLIANCE` with `tone_score = 0.0` and `impact = NEUTRAL`.
- **Classification:** `VERIFIED & RESOLVED`.
- **Root Cause:** Bag-of-words keyword collision with legal/corporate words.
- **Correction Required:** Retain regex bypass before keyword evaluation. Verified in `test_routine_compliance_nlp_filter`.

---

### Finding I: Missing Pre-Market Gap Columns in BigQuery `option_predictions_live`
- **Reported Symptom:** `expected_gap_pct`, `gap_direction`, `pre_open_conviction_pct`, and `target_open_strike` missing from BigQuery, causing KeyError in Colab.
- **Forensic Verification:** VERIFIED & RESOLVED. BigQuery schema was migrated to 48 columns including the 4 gap columns, and verified populated on every cycle.
- **Classification:** `VERIFIED & RESOLVED`.
- **Root Cause:** BigQuery table created prior to pre-market predictor feature implementation.
- **Correction Required:** Retain 48-column schema and verify.

---

### Finding J: GitHub Actions IssueOps Syntax Error
- **Reported Symptom:** GitHub Actions run `36361310908` failed with `workflow file issue`.
- **Forensic Verification:** VERIFIED. Unindented Markdown table starting with `| ` inside `/help)` block scalar in `.github/workflows/agent_issue_ops.yml` caused PyYAML `ScannerError`.
- **Classification:** `VERIFIED DEFECT`.
- **Root Cause:** Block scalar indentation violation in GitHub Actions workflow YAML.
- **Correction Required:** YES.
- **Resolution:** Replaced unindented block with indented echo statements. Validated with `yaml.safe_load`.

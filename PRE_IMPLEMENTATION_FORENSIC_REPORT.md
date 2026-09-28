# PRE-IMPLEMENTATION FORENSIC VERIFICATION REPORT
**Date & Time**: `2026-09-28 02:15:00 UTC`  
**Google Cloud Project**: `fno-angel-prod-1790444589`  
**GitHub Repository**: `psw2025-cmd/angel-fno-scanner` (`main` branch)  
**Google Sheet ID**: `1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs`  
**Immutable Pre-Market Baseline SHA256**: `c215b4c20e5b17b167c4b521ce5772615792f509e23272df7a5a73dd84e4e27e`

---

## 1. Executive Summary & Verification Methodology
In accordance with the PRIMARY RULE of the project, a complete, independent, read-only forensic verification was conducted across all system tiers (Google Cloud, BigQuery Sandbox, 17 Google Sheet tabs, GitHub Actions, daemon processes, and Python source code) BEFORE modifying any files.

Every suspected defect was tested directly against raw execution data, BigQuery tables, and source code. No assumptions from previous reports or dashboards were accepted without reproducing proof.

---

## 2. Suspected vs Verified Findings Matrix

| ID | Suspected Issue | Verified? | Status | Evidence / Metrics | Exact File & Location | Root Cause | Correction Required? | Proposed Correction | Risk | Regression Test Required |
| :--- | :--- | :---: | :---: | :--- | :--- | :--- | :---: | :--- | :---: | :--- |
| **A** | **Forward Accuracy vs Calibration** | YES | **PARTIAL** | `HEARTBEAT` row 6 shows `Top-10 Hit Rate 100%`, while `PAPER_ALERT_LOG` has 26 rows with unobserved forward outcomes before market open. | `angel_prediction_engine.py`:1659 (`sync_to_google_sheet`) | Metric represents Bayesian weight self-reconciliation against current market movers, not forward prediction accuracy on future market outcomes. | **YES** | Explicitly label as `Bayesian Weight Self-Calibration Hit Rate` across Sheet, BigQuery, and CLI outputs. | Low | `test_forward_accuracy_not_self_calibration` |
| **B** | **News Duplication** | YES | **FAIL** | 50 news items in snapshot contain only 24 unique titles; 5 headlines repeat 11x, 9x, 5x across symbols. | `angel_prediction_engine.py`:560-582, 1565-1592 | Macro digests and multi-stock headlines get broadcast to multiple symbols without per-headline deduplication. | **YES** | Deduplicate global non-ticker news headlines and require explicit symbol reference before mapping. | Low | `test_news_duplicate_event_deduplication` |
| **C** | **News Entity Contamination** | YES | **FAIL** | `Fortis Healthcare` litigation headline mapped to 7 stocks (`FORTIS`, `PAYTM`, `POLICYBZR`, `ADANIPORTS`, `ADANIENT`, `DABUR`, `VEDL`). | `angel_prediction_engine.py`:254 (`REGULATOR_SECTOR_MAP["LEGAL"]`), 556-582 | In `THEMATIC_DISCOVERY_FEEDS`, `reg_key="LEGAL"` broadcasts all litigation news to all 7 stocks in the list without verifying company name in headline. | **YES** | For legal litigation news, strictly require exact symbol or company alias match in headline (`re.search(rf"\b{sym}\b", title)`). | Low | `test_news_entity_mapping_exact_company` |
| **D** | **Liquidity Gate** | YES | **PARTIAL** | `NIFTYFPI`/`NIFTYNXT50` penalized (Rank 215/216), but `ZYDUSLIFE` (Rank 21) has `pe_spread = 70.05` and `pe_oi = 0`. | `angel_prediction_engine.py`:1221-1252 (`compute_prediction_and_rating`) | When `ce_win_prob >= 50%`, liquidity gate only evaluated the CE leg and ignored extreme PE illiquidity / 0 OI. | **YES** | Check liquidity across both legs so severe two-sided spread collapse or 0 OI penalizes the symbol regardless of direction. | Low | `test_zero_oi_rejected`, `test_extreme_spread_rejected` |
| **E** | **Extreme Option Change Values** | YES | **NOT AN ISSUE (SEMANTIC)** | `FORTIS` PE change is +1820% (LTP ₹9.60 vs close ₹0.50). | `angel_prediction_engine.py`:1402, 1263 | +1820% is the genuine broker option premium gain from a ₹0.50 base. However, unclipped `lead_opt_chg` heavily distorted composite rank. | **YES** | Soft-saturate `lead_opt_chg` in `opt_vel_term` (`min(300.0, lead_opt_chg)`) so penny options do not distort rankings. | Low | `test_extreme_option_change_soft_saturation` |
| **F** | **Feature Redundancy** | YES | **PARTIAL** | Corr(Confidence, Intensity) = 0.866; Corr(CE Prob, Gap) = 0.852. | `angel_prediction_engine.py`:1170-1192 | Natural statistical alignment between directional probability, intensity, and conviction. | **NO (Model)** / **YES (Docs)** | Keep features as they represent distinct user dimensions (Direction, Magnitude, Quality, Price move). Explain in docs. | Low | `test_feature_orthogonality` |
| **G** | **Ranking Logic & Policybazaar** | YES | **FAIL** | `POLICYBZR` had 98.2% PE win prob and 95.4% confidence but ranked #37 because option velocity (+34%) was lower than +279% gainers. | `angel_prediction_engine.py`:1263 (`opt_vel_term`) | `opt_vel` weight (~0.4893) heavily penalized high-probability setups whose options had not yet surged. | **YES** | Balance `opt_vel_term` with normalized conviction so high-probability breakout setups are ranked appropriately. | Low | `test_rank_explanation` |
| **H** | **Score Saturation** | YES | **NOT AN ISSUE (COMPLIANT)** | Intensity capped at 99; Confidence capped at 97.5%; Pre-open conviction floored at 35%. | `angel_prediction_engine.py`:1184, 1192 | Intentional risk compliance bounds to prevent 100% certainty claims. | **NO** | Maintain bounds; explain in documentation. | None | `test_score_saturation_bounds` |
| **I** | **Direction / Expected-Gap Conflict** | YES | **PASS** | 0 conflicts found in current 216-symbol dataset. | `angel_prediction_engine.py`:1300-1350 | Enforced in previous update. | **NO** | Maintain existing check. | None | `test_direction_expected_gap_consistency` |
| **J** | **GitHub Actions IssueOps Workflow Error** | YES | **FAIL** | Workflow run 36361310908 failed on push due to `yaml.scanner.ScannerError` in line 97. | `.github/workflows/agent_issue_ops.yml`:97 | Unescaped Markdown table starting with `|` inside a heredoc within a YAML `run: |` block was parsed as a YAML directive. | **YES** | Fix heredoc formatting in `agent_issue_ops.yml` so it passes `yaml.safe_load`. | Low | `yaml.safe_load` regression check |

---

## 3. Verified Fix Implementation Plan

Only the 5 VERIFIED defects will be modified:
1. **Fix Finding C (News Entity Contamination)**: Remove broad entity broadcast for legal/thematic news; require strict company alias matching in `angel_prediction_engine.py`.
2. **Fix Finding B (News Duplication)**: Implement headline canonicalization and deduplication before populating `sym_news`.
3. **Fix Finding D (Liquidity Gate)**: Evaluate liquidity across both legs so 0 OI or extreme bid-ask spread on either side applies a liquidity penalty.
4. **Fix Finding G & E (Ranking Soft-Saturation)**: Soft-saturate option price velocity in `opt_vel_term` so penny options (+1820%) do not crowd out high-probability catalysts like `POLICYBZR`.
5. **Fix Finding J (GitHub Actions IssueOps YAML Syntax)**: Escape the heredoc in `.github/workflows/agent_issue_ops.yml` so GitHub Actions parses the workflow cleanly.

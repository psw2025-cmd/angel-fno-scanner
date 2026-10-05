# Open Questions Register

This document tracks unresolved product, architecture, and operational decisions that require human or peer alignment.

---

## 1. OQ-01 — GATE-06 Formula Repair in Consumer Sheet
- **Context**: The `Formula Checks` sheet tab contains `=COUNTA(CE_PE_RANK!C3:C218)=216`. As codified in `docs/formula-checks-contract.md`, `CE_PE_RANK` is capped at 200 contracts and column C is unpopulated/option-type.
- **Question**: Should the sheet formula be updated by an automated authorized writer script (e.g. `scripts/repair_sheet_formulas.py`) or manually updated by the sheet owner in the Google Sheets UI?
- **Related Defect**: D-01, D-08

---

## 2. OQ-02 — PUBLICATION_STATUS Readback Verification
- **Context**: Incident `37081049121` produced a `FAILED_PARTIAL` row with blank digests due to the previous BigQuery INT64 schema rejection. The underlying code bug was resolved in commit `eaccdaf`.
- **Question**: Can this defect be formally closed only after a live market pre-market run produces a `VERIFIED` row with non-blank digests, or is static test suite verification in `test_publication_integrity.py` sufficient for code closure?
- **Related Defect**: D-05

---

## 3. OQ-03 — Model Calibration for Target A Gap Direction
- **Context**: Defect D-06 documents a 50% hit rate on 6 symbols in historical sheet `PREMARKET_VS_ACTUAL`.
- **Question**: What is the threshold sample size and minimum forward accuracy gate required before promoting candidate model weight adjustments into production? `AGENTS.md` Section 20 requires untouched chronological evaluation.
- **Related Defect**: D-06

---

## 4. OQ-04 — Auxiliary Pre-Close Sheet Tabs Disposition
- **Context**: `TOMORROW_EXPLOSIVE_WATCH` and `PREMARKET_VS_ACTUAL` show dates from 2026-09-29 and 2026-09-28.
- **Question**: Should these auxiliary tabs be actively maintained by the 15:10 IST pre-close GitHub Actions cron, or should they be marked with a `[LEGACY SNAPSHOT]` banner similar to `PRE_BREAKOUT_SCANNER`?
- **Related Defect**: D-07

---

## 5. OQ-05 — Live Production Stream Transition to NEW Sheet (Sheet Switch)
- **Context**: NEW sheet `1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA` has been fully provisioned and structurally aligned. It now possesses all 14 required tabs, matching OLD sheet `1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs`.
- **Status / Decision**: **DEFERRED**. The system is operating in paper mode with no financial risk. Both sheets are viable targets. The secret switch remains a zero-urgency human action when the team chooses to cut over.
- **Related Defect**: D-09 / Architectural Improvement

---

## 6. OQ-06 — Fail-Fast Schema Validator Chain Implementation
- **Context**: The D-09 schema divergence investigation led to the architecture defined in `docs/decisions/D-09_PLAN.md`.
- **Status / Decision**: **PLANNED IN `D-09_PHASES.md`**. Six sequential executable phases are defined with deliverables, unit tests, verification commands, and rollback procedures. Ready for execution beginning with Phase 1.
- **Related Defect**: D-09

---

## 7. OQ-07 — New Sheet Review & Structural Parity
- **Context**: Thorough audit was needed to determine if NEW sheet missed any structural elements present in OLD.
- **Status / Decision**: **RESOLVED VIA `docs/SHEET_FULL_DIFF.md` AND `docs/SHEET_ALIGNMENT_LOG.md`**. All formulas, headers, and tabs have been audited. `PRE_BREAKOUT_SCANNER` formulas were linked to `HEARTBEAT`, and `PRODUCTION_APPROVED` and `TOP_GAINERS` tabs were added.
- **Related Defect**: Architecture

---

## 8. OQ-08 — BigQuery Backup Table Retention Policy
- **Context**: Evaluation of the 4 backup tables in BigQuery `fno_predictions` (`market_news_sentiment_backup_cycleid_20261005_050920`, `next_day_gap_predictions_backup_cycleid_20261005_050920`, `option_predictions_live_backup_20261005`, `prediction_calibration_log_backup_cycleid_20261005_050920`).
- **Status / Decision**: **PRESERVED PER 24-HOUR AGE GATE**. Logged in `docs/BACKUP_CLEANUP_LOG.md`. All tables are under 24 hours old (1.7 to 10.4 hours old) and are retained as active rollback points until the first post-migration `prediction_cycle` executes.
- **Related Defect**: D-09 Governance

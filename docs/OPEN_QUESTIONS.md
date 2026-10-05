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

## 5. OQ-05 — Live Production Stream Transition to ANGEL_FNO_LIVE_PROD
- **Context**: Fresh production workbook `ANGEL_FNO_LIVE_PROD` (`1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA`) has been provisioned with all 12 clean tabs, verified under user quota, and formulas verified.
- **Question**: When should GitHub Actions secret `SHEET_ID` be switched from legacy `1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs` to `1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA`?
- **Related Defect**: Architectural improvement / Clutter elimination

---

## 6. OQ-06 — Application of BigQuery cycle_id Migration
- **Context**: `staging_review/migrate_bq_cycle_id.py` adds `cycle_id STRING` to `market_news_sentiment`, `next_day_gap_predictions`, and `prediction_calibration_log`.
- **Question**: Confirm permission to run `--apply` against production BigQuery dataset `fno_predictions` to restore historical logging for auxiliary tables.
- **Related Defect**: D-09

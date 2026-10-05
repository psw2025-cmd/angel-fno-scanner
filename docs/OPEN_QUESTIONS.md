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

## 5. OQ-05 — Live Production Stream Transition to ANGEL_FNO_LIVE_PROD (Sheet Switch)
- **Context**: Detailed analysis in `docs/decisions/SHEET_SWITCH.md` compared the live OLD sheet (`1Zu_9uJDQd...`, 26 tabs) with the provisioned NEW sheet (`1pI0Dp6ehEcsd...`, 12 tabs). The NEW sheet has user quota (15 GB) and includes all 12 key tabs (`FORENSIC_LIVE`, `CE_PE_RANK`, `OPTION_PREDICTIONS`, `NEWS_LIVE`, `HEARTBEAT`, `PAPER_ALERT_LOG`, `PRE_BREAKOUT_SCANNER`, `Formula Checks`, `WRITE_PROVENANCE`, `PUBLICATION_STATUS`, `PREMARKET_VS_ACTUAL`, `TOMORROW_EXPLOSIVE_WATCH`). However, `scanner.py` also writes to `PRODUCTION_APPROVED` and `TOP_GAINERS`, which are absent in NEW.
- **Question & Recommendation**: Do not switch the GitHub Actions secret `SHEET_ID` immediately. First, provision the two missing worksheets (`PRODUCTION_APPROVED` and `TOP_GAINERS`) in the NEW sheet. Second, archive historical data rows. Once validated, execute the human secret update in GitHub repository settings.
- **Related Defect**: D-09 / Architectural Improvement

---

## 6. OQ-06 — Fail-Fast Schema Validator Chain Implementation
- **Context**: The D-09 schema divergence investigation led to the architecture defined in `docs/decisions/D-09_PLAN.md`. It rejects permissive projection (`staging_review/schema_projection.py`) and outlines a 6-phase fail-fast pipeline: (1) `schemas/*.json`, (2) `tools/schema_validator.py` + tests, (3) writer wiring, (4) BigQuery `cycle_status` table, (5) `tools/pre_open_gate.py`, and (6) CI workflow enforcement.
- **Question**: Confirm start of Phase 1 implementation as the next dedicated engineering cycle.
- **Related Defect**: D-09

---

## 7. OQ-07 — Single-Writer Lease & Concurrency Governance Across Environments
- **Context**: `scanner.py` runs streaming quote loops during market hours, while pre-market and pre-close prediction cycles run periodically via GitHub Actions and local workstation scripts. Multi-writer race conditions must be prevented per `AGENTS.md` Section 13.
- **Question**: Should an explicit atomic BigQuery / Redis / Cloud Storage writer lease token be required before any writer acquires publish authority, ensuring zero collision between local workstation testing and GitHub Actions scheduled jobs?
- **Related Defect**: Architectural Governance

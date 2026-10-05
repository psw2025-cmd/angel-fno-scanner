# Agent Handoff — Current State

**Last updated:** 2026-10-05 by agy CLI (Post-Production-Run Sync)  
**Repository state:** clean, in sync / tracking origin/main  
**HEAD commit:** `14f70ca` (chore(data): auto-update daily prediction snapshots [skip ci])  
**System Mode:** PAPER / ANALYZER (No live financial risk; safe sheet modifications permitted)  

---

## 1. Current Verification Status

Run: `python tools/verify_harness.py`

Current results:
- **12 PASS (100%):**
  - `runid_type_all_string` (all 4 tables STRING)
  - `runid_latest_identical` (all 4 = 37288432509)
  - `gitsha_latest_identical` (all 4 = 9fbef9c...)
  - `writer_id_market_bot` (all 4 = market_bot)
  - `sheet_vs_bq_runid_match` (cycle matched: sheet=37288432509 bq=37288432509)
  - `sheet_vs_bq_gitsha_match` (sheet=9fbef9c... bq=9fbef9c...)
  - `forensic_live_symbol_count_219` (219)
  - `forensic_live_symbols_match_manifest` (219/219)
  - `gate_formulas_reference_populated_cells` (0 unpopulated refs)
  - `pytest_154_passed` (183 passed >= 154)
  - `git_tree_clean` (clean)
  - `git_synced_with_origin` (ahead=0 behind=0)
- **0 PENDING, 0 FAIL** (Overall: PASS 12/12)

---

## 2. Google Sheets State

- **OLD Sheet (`1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs`):** 26 tabs. Currently the active production target for `scanner.py` streaming and scheduled prediction runs.
- **NEW Sheet (`1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA`):** 14 tabs. Structurally aligned with OLD. Contains all 14 required pipeline tabs:
  - `FORENSIC_LIVE`
  - `CE_PE_RANK`
  - `OPTION_PREDICTIONS`
  - `NEWS_LIVE`
  - `HEARTBEAT`
  - `PAPER_ALERT_LOG`
  - `PRE_BREAKOUT_SCANNER` (formulas aligned in row 2 linking dynamically to `HEARTBEAT`)
  - `Formula Checks` (formulas 100% verified identical to OLD)
  - `WRITE_PROVENANCE` (read range expanded to `A1:F500` in harness to capture full streaming session history)
  - `PUBLICATION_STATUS`
  - `PREMARKET_VS_ACTUAL`
  - `TOMORROW_EXPLOSIVE_WATCH`
  - `PRODUCTION_APPROVED` (added; header structure A1:H11 initialized)
  - `TOP_GAINERS` (added; header structure A1:W4 initialized)

---

## 3. Defect Ledger Status

See `docs/DEFECT_REGISTER.md` for authoritative details:

| ID | Severity | Description | Status |
|---|---|---|---|
| D-01 | HIGH | GATE-06 in Google Sheet checks wrong column; threshold relaxed to >=200 instead of fixed | Open (Product/Sheet) |
| D-05 | HIGH | PUBLICATION_STATUS shows FAILED_PARTIAL with blank digests | Open (Pipeline) |
| D-06 | HIGH | PREMARKET_VS_ACTUAL: 50% direction accuracy on 6 symbols | Open (Model Review) |
| D-07 | LOW | TOMORROW_EXPLOSIVE_WATCH and PREMARKET_VS_ACTUAL are 6 days stale | Open (Scheduler) |
| D-08 | MEDIUM | CE_PE_RANK column C always empty; GATE-06 formula references it anyway | Open (Schema) |
| D-09 | HIGH | BigQuery auxiliary tables missing cycle_id schema field | VERIFIED_PRODUCTION (Data migration & backup complete; run 37288432509 verified with 0 NULLs; Phase 1 schemas & Phase 2 validator complete; next: Phase 3 writer wiring) |

---

## 4. Next Project: Fail-Fast Validator Chain

The permanent remediation for D-09 is phased and documented in [`docs/decisions/D-09_PHASES.md`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/docs/decisions/D-09_PHASES.md):
- **Phase 1:** Schema Registry (`schemas/*.json`) — **COMPLETED** (5 declarative schemas + `schemas/_contract.md` + `docs/DATA_CONTRACTS.md` updated from live BigQuery)
- **Phase 2:** Fail-Fast Validator (`tools/schema_validator.py` + `tests/test_schema_validator.py`) — **COMPLETED** (23 unit tests passed, 179/179 full suite passed)
- **Phase 3 (NEXT):** Writer Wiring (`angel_prediction_engine.py`)
- **Phase 4:** Cycle Status Tracking (BigQuery `cycle_status` table)
- **Phase 5:** Pre-Open Gate (`tools/pre_open_gate.py`)
- **Phase 6:** CI Workflows (`.github/workflows/`)

---

## 5. Where Full Evidence Lives

- [`docs/CHANGELOG.md`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/docs/CHANGELOG.md) — every commit, reverse chronological
- [`docs/SHEET_FULL_DIFF.md`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/docs/SHEET_FULL_DIFF.md) — complete structural and data diff between OLD and NEW sheets
- [`docs/SHEET_ALIGNMENT_LOG.md`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/docs/SHEET_ALIGNMENT_LOG.md) — log of structural formula alignment on NEW sheet
- [`docs/SHEET_TAB_ADDITIONS.md`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/docs/SHEET_TAB_ADDITIONS.md) — log of `PRODUCTION_APPROVED` and `TOP_GAINERS` additions
- [`docs/BACKUP_CLEANUP_LOG.md`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/docs/BACKUP_CLEANUP_LOG.md) — evaluation and safe retention rationale for BigQuery backup tables
- [`docs/decisions/D-09_PLAN.md`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/docs/decisions/D-09_PLAN.md) — architectural blueprint for validator chain
- [`docs/decisions/D-09_PHASES.md`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/docs/decisions/D-09_PHASES.md) — 6 executable implementation phases
- [`tools/export_cloud_database.py`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/tools/export_cloud_database.py) — permanent tool to extract all BigQuery tables, schemas, and records to a single SQLite `.db` or JSON file

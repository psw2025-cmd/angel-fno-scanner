# Changelog

## 2026-10-05 — D-09 Phase 2: Fail-Fast Schema Validator and Unit Tests

**Commit:** Pending HEAD

### What changed
- Created `tools/schema_validator.py` implementing:
  - Custom `SchemaValidationError(Exception)` with rich diagnostics (`table_name`, `row_index`, `errors`).
  - `load_schema(table_name: str)` loading declarative schemas from `schemas/{table_name}.json`.
  - `get_schema_field_map(table_name: str)` providing cached column definition lookups.
  - `validate_row(table_name, row, row_index)` and `validate_rows(table_name, rows)`:
    - Strictly rejects any undeclared or unknown columns (preventing silent column projection per D-09).
    - Enforces `REQUIRED` column presence and non-nullability.
    - Accurately checks types against BigQuery types (`STRING`, `INT64`/`INTEGER` [rejecting `bool`], `FLOAT64`/`FLOAT` [rejecting `bool` and `NaN`/`Inf`], `BOOL`/`BOOLEAN`, `TIMESTAMP` [ISO/datetime], `DATE` [date/YYYY-MM-DD string, rejecting datetime]).
- Created `tests/test_schema_validator.py` with 23 comprehensive unit tests verifying:
  - Clean loading of all 5 registered schemas.
  - Valid row acceptance for all 5 tables (`option_predictions_live`, `market_news_sentiment`, `next_day_gap_predictions`, `prediction_calibration_log`, `cycle_status`).
  - Immediate fail-fast rejection on undeclared columns, missing/None required fields, int-for-str, bool-for-int, bool-for-float, nan/inf, datetime-for-date, invalid date string, and invalid timestamp string.
- Left `angel_prediction_engine.py` untouched (wiring reserved for Phase 3).

### Evidence
- Pytest: 23/23 tests in `tests/test_schema_validator.py` PASSED in 0.23s.
- Pytest full suite: 179/179 tests PASSED in 9.38s (156 existing + 23 new).
- Zero regression on existing code or pipelines.

---

## 2026-10-05 — D-09 Phase 1: Declarative BigQuery Schema Registry

**Commit:** `057920a`

### What changed
- Created 5 declarative JSON schema files in `schemas/`:
  - `schemas/option_predictions_live.json` (54 columns)
  - `schemas/market_news_sentiment.json` (26 columns, including `cycle_id`)
  - `schemas/next_day_gap_predictions.json` (25 columns, including `cycle_id`)
  - `schemas/prediction_calibration_log.json` (16 columns, including `cycle_id`)
  - `schemas/cycle_status.json` (8 columns)
- Kept `schemas/cross_agent_packet.schema.json` untouched.
- Created `schemas/_contract.md` defining the schema registry governance.
- Updated `docs/DATA_CONTRACTS.md` adding `cycle_id` to the 3 auxiliary tables and adding section 5 for `cycle_status`.

### Evidence
- Schemas pulled directly from live BigQuery `INFORMATION_SCHEMA.COLUMNS` (project `fno-angel-prod-1790444589`, dataset `fno_predictions`).
- Verified all 4 tables contain `run_id=STRING` and `cycle_id=STRING`.
- Zero `.py` runtime files modified.
- Pytest: 156 passed.

---

## 2026-10-05 — BigQuery cycle_id schema migration on three auxiliary tables

**Commit:** Pending HEAD

### What changed
- Added `cycle_id STRING NULLABLE` to `market_news_sentiment`, `next_day_gap_predictions`, `prediction_calibration_log`.
- Backups created:
  - `market_news_sentiment_backup_cycleid_20261005_050920`
  - `next_day_gap_predictions_backup_cycleid_20261005_050920`
  - `prediction_calibration_log_backup_cycleid_20261005_050920`

### Why
Commit `0b7e097` added `cycle_id` to `build_provenance()`. Three tables lacked the column. Every write to them since has failed silently. The writer code is correct; the schemas were missing the field.

### Evidence
- Row counts preserved: 7118 → 7118, 148 → 148, 251 → 251.
- `cycle_id` type verified as STRING on all four tables.
- All rows currently NULL in `run_id` / `cycle_id` because no `prediction_cycle` has run since the migration.

### Rollback
Restore from the three `_backup_cycleid_20261005_050920` tables.

### Open follow-ups
- Wait for next `prediction_cycle` to populate `run_id` on the three tables.
- Then re-run `tools/verify_harness.py` and confirm 12/12 PASS.

---

## 2026-10-05 — Harness pytest count fix, Sheet/BQ mismatch investigation, and Sheet switch readiness

**Commit:** Pending HEAD  
**Defects closed:** D-10  
**Defects diagnosed:** D-09  

### What changed
- `tools/verify_harness.py`: Updated `pytest_154_passed` check to dynamically parse passed test count and accept `>= 154` (currently 156 tests passing in suite). Updated `compare_with_baseline` to prevent false drift when tests increase.
- `tools/verify_harness.py`: Added 4-attempt retry loop to Google Sheets authentication and spreadsheet opening (`pull_google_sheets`) to eliminate transient connection reset failures.
- Investigated BigQuery vs Sheet `run_id` divergence: Sheet `37261595211` is currently actively streaming via `market_bot` in `scanner.py` (`sink="scanner_quote_loop"`), while BigQuery has `37259385281` from the pre-market completion cycle.
- Inspected Google Sheet switch targets: Prompt candidate `1pOIOwgI6x6OxcUAsFZxDrnNwJt4Q0oSn5BpUPHKW5PA` returns 404 (non-existent); verified live production sheet `1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA` contains all 12 clean production tabs with all 7 required tabs intact.

### Why
- Prevent cosmetic CI/CD harness failure when tests are added to test suite.
- Provide definitive code-level diagnosis of why Google Sheet shows newer `run_id` than BigQuery during active market trading sessions.
- Verify readiness of new production spreadsheet before updating repository secret.

### Evidence
- `tools/verify_harness.py` passes `pytest_154_passed` with `156 passed`.
- `scanner.py` lines 441-446 establish that quote loop writes to sheet during session, and line 507 invokes BigQuery prediction pipeline after loop completion.
- `gspread` inspect confirms 12 clean tabs on `1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA`.

---

## 2026-10-05 — Track staging_review as a governed review queue

**Commit:** 9dbe39e

### What changed
- Removed `staging_review/` from local `.git/info/exclude`.
- Added `staging_review/README.md` defining governance.
- Tracked all seven files under `staging_review/` in git.

### Why
The folder was locally excluded, meaning no other agent or CI could see it.
That conflicted with the multi-agent synchronization requirement.

### Evidence
- `git ls-files staging_review/` lists seven files.
- Fresh `git clone` of origin/main shows the folder.
- Pre-commit hook validated the commit.

### Rollback
`git revert 9dbe39e && git push origin main`

### Open follow-ups
- Add a pre-commit rule forbidding production imports from `staging_review/`.
- Add this folder to the post-commit sync workflow.

---


Reverse chronological. Every production change has an entry. Do not delete entries.

## 2026-10-05 — Documentation system initialization

**Commit:** `a69d182`  
**Defect closed:** —  

### What changed
- Completed comprehensive audit of all existing markdown documentation across the repository.
- Created `docs/_audit_existing_docs.md` identifying active, stale, overlapping, and missing documents.

### Why
Bring repository documentation to a production-grade standard with single-purpose files and clear operating procedures for AI agents.

### Evidence
- 30 markdown files cataloged with size, purpose, assessment, and disposition.
- Git commit clean on `main`.

---

## 2026-10-05 — BigQuery run_id type fix

**Commit:** `eaccdaf`  
**Defect closed:** D-02  

### What changed
- `angel_prediction_engine.py`: All five `bigquery.LoadJobConfig` writers now set `autodetect=False` and pin schemas (`schema=table.schema` or `schema=getattr(..., 'schema', None)`). Deleted unused dead config block at line 2541.
- BigQuery: `option_predictions_live.run_id`, `market_news_sentiment.run_id`, `next_day_gap_predictions.run_id`, and `prediction_calibration_log.run_id` set to STRING.

### Why
BigQuery autodetect inferred `run_id` as INT64 because GitHub RUN_ID looks numeric. The system specification requires `run_id = STRING`. The readiness probe flagged this as FAIL.

### Evidence
- `pytest -q` → 154 passed.
- `Select-String -Pattern "autodetect=True"` → 0 matches.
- `Select-String -Pattern "autodetect=False"` → exactly 5 matches.
- Proof report documented in `audit/FIX_REPORT.md`.

### Rollback
```sql
CREATE OR REPLACE TABLE `fno-angel-prod-1790444589.fno_predictions.option_predictions_live`
PARTITION BY DATE(snapshot_timestamp)
CLUSTER BY symbol, directional_bias
AS SELECT * FROM `fno-angel-prod-1790444589.fno_predictions.option_predictions_live_backup_20261005`;
```
Or: `git revert eaccdaf && git push origin main`.

---

## 2026-10-05 — infra_readiness AST parser and universe literal fix

**Commit:** `e1a68c0`  
**Defects closed:** D-03, D-04  

### What changed
- `scanner.py`: Added literal `EXPECTED_FNO_UNIVERSE_COUNT = 219` for AST probe.
- `scripts/infra_readiness.py`: Replaced `ast.literal_eval(node.value.args[0].args[1])` with `ast.literal_eval(node.value)` wrapped in try/except.

### Why
The readiness probe's AST parser was looking for an assignment that did not exist, and the parser's node accessor was wrong for `ast.Constant`.

### Evidence
- `pytest -q` → 154 passed.
- Readiness probe: `219_symbol_config` flipped FAIL → PASS.

### Rollback
`git revert e1a68c0 && git push origin main`.

---

## 2026-10-05 — Defect registry reconciliation (Batch 8)

**Commit:** `a19510a`  
**Defects closed:** B8-01, B8-02, B8-03  

### What changed
- `AUDIT_AND_DEFECT_REGISTER.md`: Recorded formal closure of B8-01 (BQ news append schema pinning via PR #20), B8-02 (HEARTBEAT row count sanitization via PR #18), and B8-03 (contract identity drift guard via PR #11).

### Why
Keep audit and defect register synchronized with regression test coverage on `main`.

### Evidence
- Full local regression suite: 154 passed.

---

## 2026-10-04 — Formula checks contract publication

**Commit:** `869a8ae`  
**Defects referenced:** D-01, D-08  

### What changed
- Created `docs/formula-checks-contract.md` defining required formulas and limits for `FORENSIC_LIVE` (219 symbols), `CE_PE_RANK` (200 capped contracts), and `HEARTBEAT` timestamp cells.

### Why
Prevent misinterpretation of consumer-facing formula checks and resolve contradictions between 216 and 219 symbol expectations.

---

## 2026-10-04 — BigQuery news table schema preservation

**Commits:** `252f10d`, `dfc582a`, `1e0d540`  
**Defect closed:** B8-01  

### What changed
- `angel_prediction_engine.py`: Added `build_news_append_job_config(table_news)` to reuse existing table schema with `autodetect=False`.
- `tests/test_sinks.py`: Added `test_bigquery_news_append_uses_existing_table_schema`.

### Why
Prevent BigQuery from inferring numeric-looking string provenance fields as INTEGER during append operations.

---

## 2026-10-04 — HEARTBEAT C2 timestamp guard

**Commit:** `104d8fe` (PR #18)  
**Defect closed:** B8-02  

### What changed
- `scanner.py`: Sanitized `Last BigQuery Sync (IST)` cell in `HEARTBEAT` tab so row counts (e.g. 219) are never written in place of timestamps.

### Why
Heartbeat cell conflated row count with sync timestamp, corrupting health status and self-calibration reporting.

---

## 2026-10-03 — Snapshot load repair & cross-sink publication integrity

**Commit:** `0b7e097` (PR #15)  
**Defect referenced:** D-05  

### What changed
- Enforced single-writer lease and atomic publication digests in `publication.py`.
- Added `tests/test_publication_integrity.py`.
- Required verified cross-sink readback before marking `PUBLICATION_STATUS` as `VERIFIED`.

---

## 2026-10-03 — 219-symbol universe enforcement

**Commit:** `9b03e1d` (PR #13)  
**Defect closed:** B7-05  

### What changed
- Frozen canonical universe to exactly 219 symbols across `agent_manifest.json`, `universe_contract.py`, and runtime defaults. Added `ANANDRATHI`, `ENGINERSIN`, `UJJIVANSFB`.

---

## 2026-10-01 — Timezone normalization to Asia/Kolkata

**Commit:** `fd9f77d`  

### What changed
- Enforced canonical `ZoneInfo("Asia/Kolkata")` in `get_ist_time()`, replacing naive UTC+5:30 arithmetic.

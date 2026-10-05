# Changelog

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

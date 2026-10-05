# D-09 Fail-Fast Validator Chain — Executable Implementation Phases

**Document ID:** D-09-PHASES  
**Date:** 2026-10-05  
**Governing Architecture:** [`docs/decisions/D-09_PLAN.md`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/docs/decisions/D-09_PLAN.md)  
**Status:** READY FOR EXECUTION  

---

## 1. Executive Summary & Phasing Strategy

Defect D-09 revealed that silent schema divergence between code payloads (`**provenance` containing `cycle_id`) and BigQuery destination table definitions leads to silent write failures without interrupting CI runners. 

To permanently eradicate this risk, the implementation is decomposed into six strictly sequential, independently verifiable phases. Each phase is self-contained, backed by regression proofs, and equipped with an immediate rollback procedure. Under no circumstances will permissive projection (`staging_review/schema_projection.py`) be utilized.

---

## 2. Dependency Matrix & Effort Overview

```text
Phase 1 (Schema Registry) ──> Phase 2 (Validator Engine) ──> Phase 3 (Writer Wiring)
                                                                   │
Phase 4 (Cycle Status BQ) ─────────────────────────────────────────┤
                                                                   ▼
Phase 5 (Pre-Open Gate) <──────────────────────────────────────────┘
       │
       ▼
Phase 6 (CI Workflows)
```

| Phase | Title | Deliverables | Estimated Effort | Dependencies | Primary Verification |
|---|---|---|---|---|---|
| **Phase 1** | Schema Registry | 5 JSON schemas + contract | 1.5 hours | None | JSON schema vs BigQuery `COLUMNS` match |
| **Phase 2** | Fail-Fast Validator | `tools/schema_validator.py` + tests | 2.5 hours | Phase 1 | `pytest tests/test_schema_validator.py -v` |
| **Phase 3** | Writer Wiring | Update `angel_prediction_engine.py` | 2.0 hours | Phase 2 | `pytest -q` + simulated drift test |
| **Phase 4** | Cycle Status Tracking | BigQuery `cycle_status` table + writer hooks | 2.0 hours | Phase 3 | BigQuery insert/query verification |
| **Phase 5** | Pre-Open Gate | `tools/pre_open_gate.py` | 2.0 hours | Phase 4 | CLI execution with simulated cycle states |
| **Phase 6** | CI Workflows | GitHub Actions workflows | 2.0 hours | Phase 5 | GitHub Actions workflow run logs |

---

## 3. Detailed Phase Specifications

### Phase 1 — Schema Registry
- **Deliverables:**
  - `schemas/option_predictions_live.json`
  - `schemas/market_news_sentiment.json`
  - `schemas/next_day_gap_predictions.json`
  - `schemas/prediction_calibration_log.json`
  - `schemas/cycle_status.json`
  - `schemas/_contract.md`
- **Acceptance Criteria:**
  All JSON files are valid JSON schema definitions matching live `INFORMATION_SCHEMA.COLUMNS` from dataset `fno-angel-prod-1790444589.fno_predictions` (column names, data types, nullability).
- **Verification Command:**
  ```powershell
  python -c "import json; [json.load(open(f'schemas/{n}.json', encoding='utf-8')) for n in ['option_predictions_live', 'market_news_sentiment', 'next_day_gap_predictions', 'prediction_calibration_log', 'cycle_status']]; print('All schemas valid JSON')"
  ```
- **Rollback Procedure:**
  ```powershell
  git rm -r schemas/
  git commit -m "revert(schemas): rollback phase 1 schema registry"
  ```
- **Dependencies:** None.

---

### Phase 2 — Fail-Fast Validator
- **Deliverables:**
  - `tools/schema_validator.py`
  - `tests/test_schema_validator.py`
- **Acceptance Criteria:**
  - `validate_rows(table_name, rows)` validates required columns, data types, and rejects unknown fields immediately.
  - Unit tests achieve 100% pass rate, specifically including a regression test asserting that passing `cycle_id` into a schema missing `cycle_id` raises `SchemaValidationError`.
- **Verification Command:**
  ```powershell
  pytest tests/test_schema_validator.py -v
  ```
- **Rollback Procedure:**
  ```powershell
  git rm tools/schema_validator.py tests/test_schema_validator.py
  git commit -m "revert(validator): rollback phase 2 schema validator"
  ```
- **Dependencies:** Phase 1 (requires `schemas/*.json`).

---

### Phase 3 — Wire Validator into Writer
- **Deliverables:**
  - Modified `angel_prediction_engine.py` (and `publication.py` where applicable) calling `validate_rows` before each BigQuery `load_table_from_json` or streaming insert.
- **Acceptance Criteria:**
  - All existing unit tests pass (`pytest -q` >= 156 passed).
  - Clean python syntax compile (`python -m py_compile angel_prediction_engine.py`).
  - Pre-flight write failure occurs cleanly without calling BigQuery if payload has extra or invalid fields.
- **Verification Command:**
  ```powershell
  python -m py_compile angel_prediction_engine.py
  pytest -q
  ```
- **Rollback Procedure:**
  ```powershell
  git checkout HEAD -- angel_prediction_engine.py publication.py
  ```
- **Dependencies:** Phase 2.

---

### Phase 4 — Cycle Status Tracking
- **Deliverables:**
  - BigQuery table `cycle_status` created in `fno-angel-prod-1790444589.fno_predictions`.
  - `tools/cycle_status.py` CLI helper for query and ledger updates.
  - Writer state machine transitions (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `NOT_DUE`).
- **Acceptance Criteria:**
  - Table exists with schema: `cycle_id STRING`, `run_id STRING`, `git_sha STRING`, `sink STRING`, `status STRING`, `records_count INT64`, `error_message STRING`, `created_at TIMESTAMP`.
  - Query returns valid state records for completed operations.
- **Verification Command:**
  ```powershell
  python -c "from angel_prediction_engine import get_bigquery_client; c = get_bigquery_client(); print(list(c.query('SELECT * FROM \`fno-angel-prod-1790444589.fno_predictions.cycle_status\` LIMIT 10').result()))"
  ```
- **Rollback Procedure:**
  ```powershell
  bq rm -f -t fno-angel-prod-1790444589:fno_predictions.cycle_status
  git checkout HEAD -- tools/cycle_status.py
  ```
- **Dependencies:** Phase 3.

---

### Phase 5 — Pre-Open Gate
- **Deliverables:**
  - `tools/pre_open_gate.py`
- **Acceptance Criteria:**
  - Returns exit code 0 when all expected prediction sinks for the morning cycle are `COMPLETED`.
  - Returns exit code 2 when any expected sink has failed or is missing.
  - Handles `NOT_DUE` for pre-close sinks (e.g. `next_day_gap_predictions`) during pre-market evaluation without triggering false alarms.
- **Verification Command:**
  ```powershell
  python tools/pre_open_gate.py
  ```
- **Rollback Procedure:**
  ```powershell
  git rm tools/pre_open_gate.py
  git commit -m "revert(gate): rollback phase 5 pre-open gate"
  ```
- **Dependencies:** Phase 4.

---

### Phase 6 — CI Workflows
- **Deliverables:**
  - `.github/workflows/pr_schema_contract.yml` (validates schema files against BigQuery on PRs).
  - Modified `.github/workflows/market-bot.yml` (runs schema validation before live execution).
  - `.github/workflows/nightly_verify.yml` (runs full harness every midnight).
- **Acceptance Criteria:**
  - All three GitHub Actions workflows execute and pass cleanly on the next push.
- **Verification Command:**
  Inspect GitHub Actions workflow runs:
  ```powershell
  gh run list --limit 5
  ```
- **Rollback Procedure:**
  ```powershell
  git revert <commit-sha>
  ```
- **Dependencies:** Phase 5.

---

## 4. Operational Governance Rules
1. **One Phase Per Commit:** Every phase must be implemented in its own dedicated commit with full proof attached.
2. **Strict Test First:** Test files (`tests/test_schema_validator.py`) must be committed with the engine.
3. **No Downtime:** Staging dry runs must confirm that live quote streaming (`scanner_quote_loop`) is unaffected by validator checks.

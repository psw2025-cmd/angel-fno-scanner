# Decision: D-09 Plan — Fail-Fast Schema Validator Chain & Cycle Governance

**Defect ID:** D-09  
**Plan Date:** 2026-10-05  
**Severity:** CRITICAL  
**Status:** PROPOSED (Plan Only — Not Implemented)  

---

## 1. Executive Summary

Defect D-09 originated when commit `0b7e097` added `cycle_id` to `build_provenance()`, which was then spread via `**provenance` into all BigQuery table writes. While `option_predictions_live` was updated to include `cycle_id`, the auxiliary tables (`market_news_sentiment`, `next_day_gap_predictions`, and `prediction_calibration_log`) did not have `cycle_id` in their BigQuery schemas. Because BigQuery streaming inserts silently reject rows with unexpected fields unless configured to fail fast or audited continuously, writes to those auxiliary tables failed without stopping the runner.

The hotfix migrated the three BigQuery schemas on 2026-10-05 by adding `cycle_id STRING NULLABLE` (verified with backups). To permanently eliminate silent schema divergence, this plan establishes a declarative, fail-fast validator chain and cycle status tracker.

---

## 2. Architecture & Design

The fail-fast validator chain comprises five core components:

1. **Declarative Schemas (`schemas/*.json`):** Single authoritative JSON schema files for every BigQuery table in `fno-angel-prod-1790444589.fno_predictions`, defining column names, data types, nullability, and description.
2. **Schema Validator Engine (`tools/schema_validator.py`):** In-memory payload validator invoked by writer helpers before executing any BigQuery API call.
3. **Writer Integration:** Direct invocation within `angel_prediction_engine.py` and `publication.py` prior to BigQuery insertion. Payloads containing undeclared fields or missing non-nullable fields raise a fatal `SchemaValidationError`.
4. **Cycle Status Ledger (`cycle_status` table in BigQuery):** Append-only lifecycle tracking recording every cycle phase (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `NOT_DUE`), linking `run_id`, `cycle_id`, `git_sha`, `sink_name`, `records_written`, and `error_message`.
5. **Pre-Open Gatekeeper (`tools/pre_open_gate.py`):** Deterministic pre-market gate verifying that all due tables for the current trading day have completed successfully before downstream analyzers consume predictions.

---

## 3. Strict Operating Rules

1. **Never Silently Drop Fields (Fail-Fast Rule):** The validator must reject payloads containing extraneous columns immediately. Silently pruning unexpected columns masks upstream bugs and provenance errors.
2. **Never Break Production to Prove the Validator:** All validator code must be validated with comprehensive unit tests and staging dry-runs before deployment.
3. **Explicit Rejection of `staging_review/schema_projection.py`:** The candidate file `staging_review/schema_projection.py` is **REJECTED**. That implementation uses permissive projection (silently dropping fields not in target schemas), which is the exact anti-pattern that conceals schema divergence.
4. **Execution Order:** Test -> Wire -> Migrate -> Verify.
5. **One Phase Per Commit:** Each phase must be committed and pushed individually with dedicated verification evidence.

---

## 4. Implementation Phases & Proofs

### Phase 1: Declarative Table Schemas (`schemas/*.json`)
- **Action:** Create machine-readable JSON schema files matching BigQuery `INFORMATION_SCHEMA.COLUMNS`:
  - `schemas/option_predictions_live.json`
  - `schemas/market_news_sentiment.json`
  - `schemas/next_day_gap_predictions.json`
  - `schemas/prediction_calibration_log.json`
  - `schemas/cycle_status.json`
- **Proof Required:** Comparison script confirming 100% field, type, and nullability equivalence between JSON files and live BigQuery catalog.

### Phase 2: Schema Validator Engine & Unit Tests (`tools/schema_validator.py`)
- **Action:** Build `tools/schema_validator.py` supporting:
  - `validate_payload(table_name, record_dict)`
  - `validate_batch(table_name, list_of_records)`
  - Strict type checking (e.g., ensuring `run_id` and `cycle_id` are strings, not integers or floats)
  - Unit tests in `tests/test_schema_validator.py`, specifically including:
    - Positive validation of valid payloads.
    - Negative test: rejecting payload with unexpected `cycle_id` when schema lacks it.
    - Negative test: rejecting invalid data types.
    - Negative test: rejecting null values on required columns.
- **Proof Required:** `pytest tests/test_schema_validator.py -v` passes 100%.

### Phase 3: Wire Validator into Production Writers
- **Action:** Update `insert_into_bigquery` and auxiliary write paths in `angel_prediction_engine.py` and `publication.py`:
  - Invoke `validate_batch(table_name, rows)` before executing `client.insert_rows_json(...)`.
  - On validation error: abort write, log full diagnostic diff to `WRITE_PROVENANCE` (or stderr), and fail closed.
- **Proof Required:** Unit tests simulating writes with extra columns raise `SchemaValidationError` without triggering network requests.

### Phase 4: Create BigQuery `cycle_status` Ledger
- **Action:** Provision table `fno-angel-prod-1790444589.fno_predictions.cycle_status` with schema:
  - `cycle_id STRING REQUIRED`
  - `run_id STRING REQUIRED`
  - `git_sha STRING REQUIRED`
  - `sink STRING REQUIRED`
  - `status STRING REQUIRED` (e.g., PENDING, COMPLETED, FAILED, NOT_DUE)
  - `records_count INT64 NULLABLE`
  - `error_message STRING NULLABLE`
  - `created_at TIMESTAMP REQUIRED`
- **Proof Required:** BigQuery query verifying table creation, schema types, and successful insertion/querying of test status record.

### Phase 5: Pre-Open Production Gate (`tools/pre_open_gate.py`)
- **Action:** Implement `tools/pre_open_gate.py` to evaluate:
  - Are all sinks expected for the morning prediction cycle in state `COMPLETED`?
  - Are all `run_id` values matching across all due sinks?
  - Is `source_timestamp` within the freshness threshold (< 90 seconds during market hours)?
- **Proof Required:** Dry-run `python tools/pre_open_gate.py` with mock and live data producing accurate PASS/FAIL gate results.

### Phase 6: CI / Workflow Enforcement
- **Action:** Add validation steps to `.github/workflows/market-bot.yml` and scheduled cron workflows:
  - Schema linting step ensuring schema files match BigQuery before pipeline runs.
  - Fail-fast alerts on cycle status failures via n8n webhook or GitHub Actions annotations.
- **Proof Required:** Green workflow execution run in GitHub Actions on a non-production branch or PR.

---

## 5. Summary of Decision & Next Steps
- This plan is documented for formal peer review and governance sign-off.
- Implementation will begin at Phase 1 upon task assignment.
- Under no circumstances will silent projection (`schema_projection.py`) be adopted.

# BigQuery Schema Registry Contract

**Project:** `fno-angel-prod-1790444589`  
**Dataset:** `fno_predictions`  
**Status:** ACTIVE — AUTHORITATIVE  
**Governing Phase:** D-09 Phase 1 (Schema Registry)  

---

## 1. Purpose & Authority
The declarative JSON schema files in this directory (`schemas/*.json`) define the authoritative, immutable data contract for all tables within the BigQuery production dataset `fno_predictions`. 

No writer, bot, script, or notebook may write rows that deviate from these schema definitions.

---

## 2. Table Registry Inventory

| Schema File | Table Name | Columns | Primary Role | Write Mode |
|---|---|---|---|---|
| [`option_predictions_live.json`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/schemas/option_predictions_live.json) | `option_predictions_live` | 54 | Real-time option ranking & gap predictions (219 symbols) | `WRITE_TRUNCATE` |
| [`market_news_sentiment.json`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/schemas/market_news_sentiment.json) | `market_news_sentiment` | 26 | Multi-source tone, catalyst & sentiment scoring | `WRITE_APPEND` |
| [`next_day_gap_predictions.json`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/schemas/next_day_gap_predictions.json) | `next_day_gap_predictions` | 25 | Pre-close next-day opening gap predictions & conviction | `WRITE_APPEND` |
| [`prediction_calibration_log.json`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/schemas/prediction_calibration_log.json) | `prediction_calibration_log` | 16 | Historical prediction outcomes & weight calibration ledger | `WRITE_APPEND` |
| [`cycle_status.json`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/schemas/cycle_status.json) | `cycle_status` | 8 | Publication cycle lifecycle ledger & sink state machine | `WRITE_APPEND` |

*Note: [`cross_agent_packet.schema.json`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/schemas/cross_agent_packet.schema.json) governs GitHub Issue #3 multi-agent coordination packets.*

---

## 3. Strict Operating Rules

1. **Fail-Fast Invariant:** The writer validator (`tools/schema_validator.py`) must inspect row batches against these JSON schemas prior to calling BigQuery. Any row containing undeclared fields or mismatched types must raise an unhandled `SchemaValidationError` immediately.
2. **Rejection of Silent Projection:** Under no circumstances may columns be pruned or dropped to force an insertion into an outdated schema. Silent projection hides upstream code errors and schema divergence (the root cause of Defect D-09).
3. **Mandatory Provenance Fields:** Every table record must carry:
   - `cycle_id` (STRING)
   - `run_id` (STRING)
   - `git_sha` (STRING)
   - `writer_id` (STRING)
   - `source_timestamp` (TIMESTAMP or ISO-8601 STRING)
4. **Schema Evolution Protocol:** Adding or modifying any column requires:
   1. Creation of a timestamped BigQuery backup table (`_backup_<YYYYMMDD_HHMMSS>`).
   2. Execution of DDL `ALTER TABLE ADD COLUMN` or schema migration script.
   3. Update to the corresponding `schemas/<table_name>.json`.
   4. Update to `docs/DATA_CONTRACTS.md` and `docs/CHANGELOG.md`.
   5. Peer review and multi-agent verification before production publish.

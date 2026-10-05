# BigQuery Stale Backup Tables Cleanup Log

**Execution Date:** 2026-10-05  
**Project:** `fno-angel-prod-1790444589`  
**Dataset:** `fno_predictions`  

---

## 1. Governance Policy & Safety Checks
Per Task 4 requirements and the project safety contract:
1. Table must be created more than 24 hours ago (`age >= 24.0 hours`).
2. Current source table must exist.
3. Current source table must have equal or greater row count (`src_rows >= backup_rows`).

**Fail-Closed Rule:** If any check fails, do not delete the backup. Report and preserve.

---

## 2. Backup Tables Audit Results

| Backup Table ID | Created (UTC) | Age (Hours) | Age >= 24h? | Source Table | Source Exists? | Source Rows | Backup Rows | Rows OK? | Outcome |
|---|---|---|---|---|---|---|---|---|---|
| `market_news_sentiment_backup_cycleid_20261005_050920` | 2026-10-05 05:09:27 | 1.66 | **FAIL** | `market_news_sentiment` | YES | 7,118 | 7,118 | YES | **PRESERVED** |
| `next_day_gap_predictions_backup_cycleid_20261005_050920` | 2026-10-05 05:09:29 | 1.66 | **FAIL** | `next_day_gap_predictions` | YES | 148 | 148 | YES | **PRESERVED** |
| `option_predictions_live_backup_20261005` | 2026-10-04 20:23:38 | 10.42 | **FAIL** | `option_predictions_live` | YES | 219 | 219 | YES | **PRESERVED** |
| `prediction_calibration_log_backup_cycleid_20261005_050920` | 2026-10-05 05:09:30 | 1.66 | **FAIL** | `prediction_calibration_log` | YES | 251 | 251 | YES | **PRESERVED** |

---

## 3. Summary of Actions Taken

- **Tables Deleted (0):** None
- **Tables Kept (4):**
  - `market_news_sentiment_backup_cycleid_20261005_050920`
  - `next_day_gap_predictions_backup_cycleid_20261005_050920`
  - `option_predictions_live_backup_20261005`
  - `prediction_calibration_log_backup_cycleid_20261005_050920`
- **Rationale for Retention:**
  None of the backup tables meet the 24-hour age threshold. Specifically, the three `cycle_id` migration backups are only ~1.7 hours old and must remain available as rollback points until the first post-migration `prediction_cycle` executes and populates live data.
- **Next Re-evaluation:**
  Eligible for cleanup on or after 2026-10-06 05:10:00 UTC, conditional upon successful post-migration prediction cycle execution.

# Google Sheets & BigQuery Cross-Sink Reconciliation Report

**Audit Time (IST)**: `2026-10-09T14:56:44.802205+05:30`  
**Reconciliation Status**: `🔴 FAIL_CLOSED`  
**Canonical Google Sheet**: `1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs`  
**BigQuery Destination**: `fno-angel-prod-1790444589.fno_predictions.option_predictions_live`  
**Target Run ID**: `37900561389`  

---

## 1. Google Sheets (`OPTION_SHEET`) Evidence
- **Spreadsheet Title**: `OPTION_SHEET`
- **FORENSIC_LIVE Row Count**: `219`
- **FORENSIC_LIVE Unique Symbols**: `219`
- **CE_PE_RANK Data Rows**: `202`
- **Sample Timestamp**: `2026-10-09 13:21:47`
- **Tab Inspection Status**: `FAIL`

---

## 2. BigQuery (`fno_predictions.option_predictions_live`) Evidence
- **Table Total Rows**: `219`
- **Distinct Symbols Count**: `219`
- **Oldest Exchange Timestamp**: `2026-10-09 07:51:47.904794+00:00`
- **Newest Exchange Timestamp**: `2026-10-09 07:51:47.904794+00:00`
- **Table Inspection Status**: `PASS`

---

## 3. Reconciliation & Parity Verification
| Check | Sheets Value | BigQuery Value | Result |
| :--- | :---: | :---: | :---: |
| **Universe Symbol Count** | `219` | `219` | `PASS` |
| **Row Count Alignment** | `219` | `219` | `PASS` |
| **219-Symbol Full Universe** | 219 | 219 | `PASS` |

---

## 4. Machine-Readable Raw Audit Payload
```json
{
  "audit_timestamp_ist": "2026-10-09T14:56:44.802205+05:30",
  "status": "FAIL_CLOSED",
  "canonical_sheet_id": "1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs",
  "bigquery_table": "fno-angel-prod-1790444589.fno_predictions.option_predictions_live",
  "target_run_id": "37900561389",
  "sheets": {
    "status": "FAIL",
    "spreadsheet_title": "OPTION_SHEET",
    "forensic_live_rows": 219,
    "forensic_distinct_symbols": 219,
    "ce_pe_rank_data_rows": 202,
    "sample_symbol": "GLENMARK",
    "sample_timestamp": "2026-10-09 13:21:47"
  },
  "bigquery": {
    "status": "PASS",
    "table_num_rows": 219,
    "query_total_rows": 219,
    "distinct_symbols": 219,
    "oldest_timestamp": "2026-10-09 07:51:47.904794+00:00",
    "newest_timestamp": "2026-10-09 07:51:47.904794+00:00"
  },
  "reconciliation": {
    "universe_parity": true,
    "sheets_symbols_count": 219,
    "bigquery_symbols_count": 219,
    "row_count_match": true,
    "live_universe_qualified": true
  }
}
```

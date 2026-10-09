# Google Sheets & BigQuery Cross-Sink Reconciliation Report

**Audit Time (IST)**: `2026-10-09T16:26:26.686638+05:30`  
**Reconciliation Status**: `🟢 PASS`  
**Canonical Google Sheet**: `1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs`  
**BigQuery Destination**: `fno-angel-prod-1790444589.fno_predictions.option_predictions_live`  
**Target Run ID**: `37900561389`  

---

## 1. Google Sheets (`OPTION_SHEET`) Evidence
- **Spreadsheet Title**: `OPTION_SHEET`
- **FORENSIC_LIVE Row Count**: `219`
- **FORENSIC_LIVE Unique Symbols**: `219`
- **CE_PE_RANK Data Rows**: `200`
- **Sample Timestamp**: `2026-10-09 16:22:12`
- **Tab Inspection Status**: `PASS`

---

## 2. BigQuery (`fno_predictions.option_predictions_live`) Evidence
- **Table Total Rows**: `219`
- **Distinct Symbols Count**: `219`
- **Oldest Exchange Timestamp**: `2026-10-09 10:52:12.538301+00:00`
- **Newest Exchange Timestamp**: `2026-10-09 10:52:12.538301+00:00`
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
  "audit_timestamp_ist": "2026-10-09T16:26:26.686638+05:30",
  "status": "PASS",
  "canonical_sheet_id": "1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs",
  "bigquery_table": "fno-angel-prod-1790444589.fno_predictions.option_predictions_live",
  "target_run_id": "37900561389",
  "sheets": {
    "status": "PASS",
    "spreadsheet_title": "OPTION_SHEET",
    "forensic_live_rows": 219,
    "forensic_distinct_symbols": 219,
    "ce_pe_rank_data_rows": 200,
    "sample_symbol": "PERSISTENT",
    "sample_timestamp": "2026-10-09 16:22:12"
  },
  "bigquery": {
    "status": "PASS",
    "table_num_rows": 219,
    "query_total_rows": 219,
    "distinct_symbols": 219,
    "oldest_timestamp": "2026-10-09 10:52:12.538301+00:00",
    "newest_timestamp": "2026-10-09 10:52:12.538301+00:00"
  },
  "reconciliation": {
    "universe_parity": true,
    "symbol_exact_match": true,
    "checksum_match": true,
    "sheets_symbols_count": 219,
    "bigquery_symbols_count": 219,
    "row_count_match": true,
    "timestamp_match": true,
    "run_id_match": true,
    "symbol_hash_parity_verified": true,
    "live_universe_qualified": true,
    "run_id_parity_verified": true,
    "exchange_timestamp_parity_verified": true,
    "adaniensol_present": true,
    "adanipower_present": true,
    "ntpc_present": true
  },
  "checksum_sha256_16": "3f6153d1e221ae43"
}
```

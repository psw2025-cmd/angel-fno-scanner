# Google Sheets & BigQuery Cross-Sink Reconciliation Report

**Audit Time (IST)**: `2026-10-26T05:19:35.225135+05:30`
**Reconciliation Status**: `[PASS]`
**Canonical Google Sheet**: `1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs`
**BigQuery Destination**: `fno-angel-prod-1790444589.fno_predictions.option_predictions_live`
**Target Run ID**: `39806853848`

---

## 1. Google Sheets (`OPTION_SHEET`) Evidence
- **Spreadsheet Title**: `OPTION_SHEET`
- **FORENSIC_LIVE Row Count**: `219`
- **FORENSIC_LIVE Unique Symbols**: `219`
- **CE_PE_RANK Data Rows**: `200`
- **Sample Timestamp**: `2026-10-22 21:14:07`
- **Provenance Run ID**: `39806853848`
- **Provenance Git SHA**: `32d9b3a34e9ee759185bc6aed1517e0ec83bed6b`
- **Provenance Writer ID**: `market_bot`
- **Tab Inspection Status**: `PASS`

---

## 2. BigQuery (`fno_predictions.option_predictions_live`) Evidence
- **Table Total Rows**: `219`
- **Distinct Symbols Count**: `219`
- **Oldest Exchange Timestamp**: `2026-10-22 15:44:07.017813+00:00`
- **Newest Exchange Timestamp**: `2026-10-22 15:44:07.017813+00:00`
- **Provenance Run ID**: `39806853848`
- **Provenance Git SHA**: `32d9b3a34e9ee759185bc6aed1517e0ec83bed6b`
- **Provenance Writer ID**: `market_bot`
- **Provenance Snapshot Timestamp**: `2026-10-22 15:44:07.017813+00:00`
- **Table Inspection Status**: `PASS`

---

## 3. Reconciliation & Parity Verification
| Check | Sheets Value | BigQuery Value | Result |
| :--- | :---: | :---: | :---: |
| **Universe Symbol Count** | `219` | `219` | `PASS` |
| **Row Count Alignment** | `219` | `219` | `PASS` |
| **Symbol SHA-256 Prefix** | `3f6153d1e221ae43` | `3f6153d1e221ae43` | `PASS` |
| **Run ID Parity** | `39806853848` | `39806853848` | `PASS` |
| **Git SHA Parity** | `32d9b3a34e9ee759185bc6aed1517e0ec83bed6b` | `32d9b3a34e9ee759185bc6aed1517e0ec83bed6b` | `PASS` |
| **Writer ID Parity** | `market_bot` | `market_bot` | `PASS` |
| **Timestamp Parity (<=120s)** | `2026-10-22 21:14:07` | `2026-10-22 15:44:07.017813+00:00` | `PASS` |

---

## 4. Machine-Readable Raw Audit Payload
```json
{
  "audit_timestamp_ist": "2026-10-26T05:19:35.225135+05:30",
  "status": "PASS",
  "canonical_sheet_id": "1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs",
  "bigquery_table": "fno-angel-prod-1790444589.fno_predictions.option_predictions_live",
  "target_run_id": "39806853848",
  "sheets": {
    "status": "PASS",
    "spreadsheet_title": "OPTION_SHEET",
    "forensic_live_rows": 219,
    "forensic_distinct_symbols": 219,
    "ce_pe_rank_data_rows": 200,
    "sample_symbol": "OIL",
    "sample_timestamp": "2026-10-22 21:14:07",
    "provenance_run_id": "39806853848",
    "provenance_git_sha": "32d9b3a34e9ee759185bc6aed1517e0ec83bed6b",
    "provenance_writer_id": "market_bot",
    "provenance_published_at_ist": "2026-10-22 21:14:07"
  },
  "bigquery": {
    "status": "PASS",
    "table_num_rows": 219,
    "query_total_rows": 219,
    "distinct_symbols": 219,
    "oldest_timestamp": "2026-10-22 15:44:07.017813+00:00",
    "newest_timestamp": "2026-10-22 15:44:07.017813+00:00",
    "provenance_run_id": "39806853848",
    "provenance_git_sha": "32d9b3a34e9ee759185bc6aed1517e0ec83bed6b",
    "provenance_writer_id": "market_bot",
    "provenance_snapshot_timestamp": "2026-10-22 15:44:07.017813+00:00"
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
    "git_sha_match": true,
    "writer_id_match": true,
    "symbol_hash_parity_verified": true,
    "live_universe_qualified": true,
    "run_id_parity_verified": true,
    "exchange_timestamp_parity_verified": true,
    "provenance_time_delta_seconds": 0.017813,
    "sheet_run_id": "39806853848",
    "bigquery_run_id": "39806853848",
    "sheet_git_sha": "32d9b3a34e9ee759185bc6aed1517e0ec83bed6b",
    "bigquery_git_sha": "32d9b3a34e9ee759185bc6aed1517e0ec83bed6b",
    "sheet_writer_id": "market_bot",
    "bigquery_writer_id": "market_bot",
    "adaniensol_present": true,
    "adanipower_present": true,
    "ntpc_present": true
  },
  "checksum_sha256_16": "3f6153d1e221ae43"
}
```

# Architectural Decision: Production Google Sheet Transition (OLD vs NEW)

## Context & Problem Statement
The current live production Google Sheet workbook (`1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs`) was created during initial system development and has accumulated 26 tabs, including clutter (`Sheet1`, `Sheet2`, `Sheet3`), dead legacy objects (`LEGACY_F&O_DASHBOARD_OBJECT`, `Cloud_Automation_Setup`), and one-off audit snapshots (`E2E_AUDIT_20260928`).

A clean, autonomous production workbook (`1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA`, titled `ANGEL_FNO_LIVE_PROD`) was provisioned under the user account (`warghade2012@gmail.com`) inside Google Drive folder `SYSTEM3_TEMP_EXCHANGE` (`13gCmRRUjarvUlKJ1bR9FZw-ki8IJ7bzX`), with full Editor permissions granted to service account `angel-sheets-bot@fno-angel-prod-1790444589.iam.gserviceaccount.com`.

Before switching the GitHub Actions repository secret `SHEET_ID`, this document provides an exhaustive inventory, writer dependency matrix, and gap analysis.

---

## 1. Sheet Inventory Comparison

| Property | OLD Workbook | NEW Workbook |
| :--- | :--- | :--- |
| **Title** | `OPTION_SHEET` | `ANGEL_FNO_LIVE_PROD` |
| **Spreadsheet ID** | `1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs` | `1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA` |
| **Owner** | User Account | User Account (`warghade2012@gmail.com`) |
| **Total Tabs** | 26 tabs | 12 clean tabs |
| **Legacy Clutter** | High (14 unmaintained/one-off tabs) | Zero clutter |

### Tab Lists
* **OLD Workbook Tabs (26):**
  1. `PRE_BREAKOUT_SCANNER`
  2. `Sheet1`
  3. `F&O Options Top Gainers Tracker Dashboard`
  4. `LEGACY_F&O_DASHBOARD_OBJECT`
  5. `Formula Checks`
  6. `PRODUCTION_APPROVED`
  7. `Cloud_Automation_Setup`
  8. `FORENSIC_LIVE`
  9. `HEARTBEAT`
  10. `CE_PE_RANK`
  11. `NSE_EVENTS`
  12. `PAPER_ALERT_LOG`
  13. `NEWS_LIVE`
  14. `NEWS_IMPACT`
  15. `NEWS_TYPE_TALLY`
  16. `TOP_GAINERS`
  17. `OPTION_PREDICTIONS`
  18. `E2E_AUDIT_20260928`
  19. `MARKET_LEARNINGS_20260928`
  20. `PREDICTION_VALIDATION`
  21. `PREMARKET_VS_ACTUAL`
  22. `TOMORROW_EXPLOSIVE_WATCH`
  23. `WRITE_PROVENANCE`
  24. `PUBLICATION_STATUS`
  25. `Sheet2`
  26. `Sheet3`

* **NEW Workbook Tabs (12):**
  1. `FORENSIC_LIVE`
  2. `CE_PE_RANK`
  3. `OPTION_PREDICTIONS`
  4. `NEWS_LIVE`
  5. `HEARTBEAT`
  6. `PAPER_ALERT_LOG`
  7. `PRE_BREAKOUT_SCANNER`
  8. `Formula Checks`
  9. `WRITE_PROVENANCE`
  10. `PUBLICATION_STATUS`
  11. `PREMARKET_VS_ACTUAL`
  12. `TOMORROW_EXPLOSIVE_WATCH`

---

## 2. Writer Dependency Analysis

Codebase examination of writer entrypoints:

1. **`writer_guard.py`:**
   - Writes to: `WRITE_PROVENANCE`
   - Status on NEW: **Present**

2. **`publication.py`:**
   - Writes to: `PUBLICATION_STATUS`
   - Status on NEW: **Present**

3. **`angel_prediction_engine.py`:**
   - Writes to: `FORENSIC_LIVE`, `HEARTBEAT`, `NEWS_LIVE`, `OPTION_PREDICTIONS`, `PAPER_ALERT_LOG`, `PRE_BREAKOUT_SCANNER`
   - Status on NEW: **All 6 Present**

4. **`tools/verify_harness.py`:**
   - Reads: `FORENSIC_LIVE`, `CE_PE_RANK`, `Formula Checks`, `WRITE_PROVENANCE`, `PUBLICATION_STATUS`, `PREMARKET_VS_ACTUAL`, `TOMORROW_EXPLOSIVE_WATCH`
   - Status on NEW: **All 7 Present** (and formulas verified)

5. **`scanner.py`:**
   - Writes to: `FORENSIC_LIVE`, `HEARTBEAT`, `CE_PE_RANK`, `PAPER_ALERT_LOG`, `TOP_GAINERS`, `PRODUCTION_APPROVED`
   - Note on `scanner.py`: `worksheet()` helper automatically creates missing worksheets via `add_worksheet()` if not found, but to eliminate runtime overhead, `PRODUCTION_APPROVED` and `TOP_GAINERS` should be pre-created.

---

## 3. Gap Analysis

1. **Tabs in OLD containing active data missing in NEW:**
   - `PRODUCTION_APPROVED`: Contains rendered paper trade execution summaries from `scanner.py`.
   - `TOP_GAINERS`: Contains duplicate output of `CE_PE_RANK` written by `publish_gainers()`.
2. **Tabs in OLD containing historical/one-off records (not required by runtime):**
   - `E2E_AUDIT_20260928`, `MARKET_LEARNINGS_20260928`, `PREDICTION_VALIDATION`
3. **Tabs in OLD that are pure clutter:**
   - `Sheet1`, `Sheet2`, `Sheet3`, `Cloud_Automation_Setup`, `LEGACY_F&O_DASHBOARD_OBJECT`

---

## 4. Recommendation

1. **Pre-provision `PRODUCTION_APPROVED` and `TOP_GAINERS` on NEW:**  
   Copy the existing schema/data for `PRODUCTION_APPROVED` and `TOP_GAINERS` into `1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA` so `scanner.py` writes into them seamlessly.
2. **Switch Secret Post-Market Close (or during market lull):**  
   Update GitHub Actions repository secret `SHEET_ID` to `1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA`.
3. **Retire OLD Sheet to Read-Only:**  
   Rename old workbook title to `OPTION_SHEET_LEGACY_ARCHIVE` to prevent confusion.

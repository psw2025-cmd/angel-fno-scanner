# Google Sheet Tab Additions Log

**Execution Date:** 2026-10-05  
**OLD Sheet ID (Reference):** `1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs` (26 tabs)  
**NEW Sheet ID (Target):** `1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA` (14 tabs)  

---

## 1. Overview & Objective
Ensure that both Google Sheets contain all 14 required tabs utilized across the publisher and analysis codebase (`writer_guard.py`, `angel_prediction_engine.py`, `scanner.py`, and `publication.py`).

---

## 2. Required Tabs Audit Matrix

| Tab Name | Required By | Status on OLD | Status on NEW (Pre) | Action Taken | Final Status (NEW) |
|---|---|---|---|---|---|
| `FORENSIC_LIVE` | `scanner.py`, `publication.py` | Present | Present | None | Present |
| `CE_PE_RANK` | `scanner.py`, `publication.py` | Present | Present | None | Present |
| `OPTION_PREDICTIONS` | `angel_prediction_engine.py` | Present | Present | None | Present |
| `NEWS_LIVE` | `scanner.py`, `publication.py` | Present | Present | None | Present |
| `HEARTBEAT` | `scanner.py` | Present | Present | None | Present |
| `PAPER_ALERT_LOG` | `scanner.py` | Present | Present | None | Present |
| `PRE_BREAKOUT_SCANNER` | `scanner.py` | Present | Present | None | Present |
| `Formula Checks` | `tools/verify_harness.py` | Present | Present | None | Present |
| `WRITE_PROVENANCE` | `writer_guard.py` | Present | Present | None | Present |
| `PUBLICATION_STATUS` | `publication.py` | Present | Present | None | Present |
| `PREMARKET_VS_ACTUAL` | `angel_prediction_engine.py` | Present | Present | None | Present |
| `TOMORROW_EXPLOSIVE_WATCH` | `angel_prediction_engine.py` | Present | Present | None | Present |
| `PRODUCTION_APPROVED` | `scanner.py` | Present | **MISSING** | Created worksheet; copied header rows 1–11 from OLD | **Present** |
| `TOP_GAINERS` | `scanner.py` | Present | **MISSING** | Created worksheet; copied header rows 1–4 from OLD | **Present** |

---

## 3. Detailed Additions to NEW Sheet

1. **`PRODUCTION_APPROVED`**:
   - Created in NEW workbook `1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA`
   - Allocated dimensions: 500 rows, 20 columns
   - Applied header block (`A1:H11`): Title, methodology description, summary KPI placeholders (`As of`, `Filled outcomes`, `Wins`, `Losses`, `Win rate`, `Average follow-through`), and table headers (`Logged at IST`, `Session date`, `Symbol`, `Side`, `Entry session change %`, `Later session change %`, `Follow-through`, `Outcome filled at`).
   - Data rows: Stays empty (no historical trade outcomes copied).

2. **`TOP_GAINERS`**:
   - Created in NEW workbook `1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA`
   - Allocated dimensions: 500 rows, 30 columns
   - Applied header block (`A1:W4`): Title, feed metadata description, blank separator, and all 23 gainer column headers (`Contract`, `Underlying`, `Type`, `Strike`, `Expiry`, `Live LTP`, `Prev close`, `Prev close basis`, `Net chg`, `Gain %`, `Volume`, `Open interest`, `Best bid`, `Best ask`, `Intrinsic`, `Time value`, `Break-even`, `Black-76 IV %`, `Black-76 delta`, `Black-76 theta per day`, `Momentum`, `Momentum basis`, `Exchange time`).
   - Data rows: Stays empty (no contract rows copied).

---

## 4. Final Tab Lists

- **Tabs Added to OLD:** None (0)
- **Tabs Added to NEW:** `PRODUCTION_APPROVED`, `TOP_GAINERS` (2)
- **OLD Sheet Total Tabs (26):** `PRE_BREAKOUT_SCANNER`, `Sheet1`, `F&O Options Top Gainers Tracker Dashboard`, `LEGACY_F&O_DASHBOARD_OBJECT`, `Formula Checks`, `PRODUCTION_APPROVED`, `Cloud_Automation_Setup`, `FORENSIC_LIVE`, `HEARTBEAT`, `CE_PE_RANK`, `NSE_EVENTS`, `PAPER_ALERT_LOG`, `NEWS_LIVE`, `NEWS_IMPACT`, `NEWS_TYPE_TALLY`, `TOP_GAINERS`, `OPTION_PREDICTIONS`, `E2E_AUDIT_20260928`, `MARKET_LEARNINGS_20260928`, `PREDICTION_VALIDATION`, `PREMARKET_VS_ACTUAL`, `TOMORROW_EXPLOSIVE_WATCH`, `WRITE_PROVENANCE`, `PUBLICATION_STATUS`, `Sheet2`, `Sheet3`
- **NEW Sheet Total Tabs (14):** `FORENSIC_LIVE`, `CE_PE_RANK`, `OPTION_PREDICTIONS`, `NEWS_LIVE`, `HEARTBEAT`, `PAPER_ALERT_LOG`, `PRE_BREAKOUT_SCANNER`, `Formula Checks`, `WRITE_PROVENANCE`, `PUBLICATION_STATUS`, `PREMARKET_VS_ACTUAL`, `TOMORROW_EXPLOSIVE_WATCH`, `PRODUCTION_APPROVED`, `TOP_GAINERS`

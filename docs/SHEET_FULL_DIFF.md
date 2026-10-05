# Comprehensive Google Sheet Comparison Report — OLD vs NEW

**Execution Date:** 2026-10-05  
**OLD Sheet ID (Live):** `1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs` (26 tabs)  
**NEW Sheet ID (Prepared):** `1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA` (12 tabs)  

---

## Section 1: Tab Inventory

| Tab Name | Present in OLD? | Present in NEW? | Data Rows (OLD) | Data Rows (NEW) | Hidden (OLD) | Hidden (NEW) |
|---|---|---|---|---|---|---|
| `CE_PE_RANK` | YES | YES | 203 | 203 | No | No |
| `Cloud_Automation_Setup` | YES | NO | 21 | N/A | No | No |
| `E2E_AUDIT_20260928` | YES | NO | 52 | N/A | No | No |
| `F&O Options Top Gainers Tracker Dashboard` | YES | NO | 38 | N/A | No | No |
| `FORENSIC_LIVE` | YES | YES | 220 | 220 | No | No |
| `Formula Checks` | YES | YES | 10 | 10 | No | No |
| `HEARTBEAT` | YES | YES | 9 | 9 | No | No |
| `LEGACY_F&O_DASHBOARD_OBJECT` | YES | NO | 11 | N/A | No | No |
| `MARKET_LEARNINGS_20260928` | YES | NO | 17 | N/A | No | No |
| `NEWS_IMPACT` | YES | NO | 379 | N/A | No | No |
| `NEWS_LIVE` | YES | YES | 221 | 221 | No | No |
| `NEWS_TYPE_TALLY` | YES | NO | 9 | N/A | No | No |
| `NSE_EVENTS` | YES | NO | 308 | N/A | No | No |
| `OPTION_PREDICTIONS` | YES | YES | 254 | 254 | No | No |
| `PAPER_ALERT_LOG` | YES | YES | 500 | 500 | No | No |
| `PREDICTION_VALIDATION` | YES | NO | 52 | N/A | No | No |
| `PREMARKET_VS_ACTUAL` | YES | YES | 10 | 10 | No | No |
| `PRE_BREAKOUT_SCANNER` | YES | YES | 25 | 25 | No | No |
| `PRODUCTION_APPROVED` | YES | NO | 498 | N/A | No | No |
| `PUBLICATION_STATUS` | YES | YES | 2 | 2 | No | No |
| `Sheet1` | YES | NO | 203 | N/A | No | No |
| `Sheet2` | YES | NO | 10 | N/A | No | No |
| `Sheet3` | YES | NO | 10 | N/A | No | No |
| `TOMORROW_EXPLOSIVE_WATCH` | YES | YES | 16 | 16 | No | No |
| `TOP_GAINERS` | YES | NO | 203 | N/A | No | No |
| `WRITE_PROVENANCE` | YES | YES | 37 | 13 | No | No |

---

## Section 2: Tabs Missing From Each Side

### Missing in NEW (14 tabs from OLD):
- `Sheet1` (Rows in OLD: 203)
- `F&O Options Top Gainers Tracker Dashboard` (Rows in OLD: 38)
- `LEGACY_F&O_DASHBOARD_OBJECT` (Rows in OLD: 11)
- `PRODUCTION_APPROVED` (Rows in OLD: 498)
- `Cloud_Automation_Setup` (Rows in OLD: 21)
- `NSE_EVENTS` (Rows in OLD: 308)
- `NEWS_IMPACT` (Rows in OLD: 379)
- `NEWS_TYPE_TALLY` (Rows in OLD: 9)
- `TOP_GAINERS` (Rows in OLD: 203)
- `E2E_AUDIT_20260928` (Rows in OLD: 52)
- `MARKET_LEARNINGS_20260928` (Rows in OLD: 17)
- `PREDICTION_VALIDATION` (Rows in OLD: 52)
- `Sheet2` (Rows in OLD: 10)
- `Sheet3` (Rows in OLD: 10)

### Missing in OLD (0 tabs from NEW):
- None (all tabs in NEW exist in OLD)

---

## Section 3: Header Differences Per Tab

All 12 common tabs have identical headers across both sheets.

---

## Section 4: Formula Differences Per Tab

### Tab `PRE_BREAKOUT_SCANNER`
- **OLD Formulas (first 3 rows):** ['=HEARTBEAT!A2', '=HEARTBEAT!B2', '=HEARTBEAT!C2', '=HEARTBEAT!D2']
- **NEW Formulas (first 3 rows):** []

---

## Section 5: Data Validation and Conditional Formatting Differences

| Tab Name | Conditional Rules (OLD) | Conditional Rules (NEW) | Protected Ranges (OLD) | Protected Ranges (NEW) | Named Ranges (OLD) | Named Ranges (NEW) |
|---|---|---|---|---|---|---|
| `CE_PE_RANK` | 0 | 0 | 0 | 0 | 0 | 0 |
| `FORENSIC_LIVE` | 0 | 0 | 0 | 0 | 0 | 0 |
| `Formula Checks` | 0 | 0 | 0 | 0 | 0 | 0 |
| `HEARTBEAT` | 0 | 0 | 0 | 0 | 0 | 0 |
| `NEWS_LIVE` | 0 | 0 | 0 | 0 | 0 | 0 |
| `OPTION_PREDICTIONS` | 0 | 0 | 0 | 0 | 0 | 0 |
| `PAPER_ALERT_LOG` | 0 | 0 | 0 | 0 | 0 | 0 |
| `PREMARKET_VS_ACTUAL` | 0 | 0 | 0 | 0 | 0 | 0 |
| `PRE_BREAKOUT_SCANNER` | 0 | 0 | 0 | 0 | 0 | 0 |
| `PUBLICATION_STATUS` | 0 | 0 | 0 | 0 | 0 | 0 |
| `TOMORROW_EXPLOSIVE_WATCH` | 0 | 0 | 0 | 0 | 0 | 0 |
| `WRITE_PROVENANCE` | 0 | 0 | 0 | 0 | 0 | 0 |

---

## Section 6: Sample Data Shape (Last 5 Rows of WRITE_PROVENANCE from OLD)

| Row | Source Timestamp | Run ID | Git SHA | Writer ID | Sink | Record Count |
|---|---|---|---|---|---|---|
| 1 | 2026-10-05 11:29:21 | 37261595211 | d425b45... | market_bot | `scanner_quote_loop` | 219 |
| 2 | 2026-10-05 11:35:13 | 37261595211 | d425b45... | market_bot | `scanner_quote_loop` | 219 |
| 3 | 2026-10-05 11:41:04 | 37261595211 | d425b45... | market_bot | `scanner_quote_loop` | 219 |
| 4 | 2026-10-05 11:47:21 | 37261595211 | d425b45... | market_bot | `scanner_quote_loop` | 219 |
| 5 | 2026-10-05 11:53:20 | 37261595211 | d425b45... | market_bot | `scanner_quote_loop` | 219 |

---

## Section 7: Summary and Recommended Changes

1. **Core Pipeline Coverage:** All 12 tabs required for live streaming and core prediction logging exist on NEW (`FORENSIC_LIVE`, `CE_PE_RANK`, `OPTION_PREDICTIONS`, `NEWS_LIVE`, `HEARTBEAT`, `PAPER_ALERT_LOG`, `PRE_BREAKOUT_SCANNER`, `Formula Checks`, `WRITE_PROVENANCE`, `PUBLICATION_STATUS`, `PREMARKET_VS_ACTUAL`, `TOMORROW_EXPLOSIVE_WATCH`).
2. **Required Writer Tabs Missing in NEW:** `scanner.py` writes to `PRODUCTION_APPROVED` and `TOP_GAINERS`. Both exist in OLD with populated structures but are missing in NEW.
3. **Extraneous Tabs in OLD:** OLD contains 12 non-critical historical or utility tabs (`Sheet1`, `Sheet2`, `Sheet3`, `F&O Options Top Gainers Tracker Dashboard`, `LEGACY_F&O_DASHBOARD_OBJECT`, `Cloud_Automation_Setup`, `NSE_EVENTS`, `NEWS_IMPACT`, `NEWS_TYPE_TALLY`, `E2E_AUDIT_20260928`, `MARKET_LEARNINGS_20260928`, `PREDICTION_VALIDATION`). These do not need to be replicated in NEW.
4. **Action Items:**
   - Create `PRODUCTION_APPROVED` in NEW copying headers from OLD.
   - Create `TOP_GAINERS` in NEW copying headers from OLD.
   - Verify all formulas in `Formula Checks` on NEW evaluate correctly.

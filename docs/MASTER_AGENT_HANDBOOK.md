# Angel F&O Scanner — Complete Master Agent Handbook & Knowledge Base

> **Target Audience:** All current and future AI agents, CLI agents (agy), automated runners, and developers.  
> **Permanent Authoritative File:** Saved locally at `C:\temp\ANGEL_FNO_COMPLETE_AGENT_HANDBOOK.md` and repository `docs/MASTER_AGENT_HANDBOOK.md`.  
> **Repository:** `psw2025-cmd/angel-fno-scanner` on branch `main`  
> **Coordination Bus:** GitHub Issue #3 — Canonical Cross-Agent Control Bus  
> **Operating Mode:** `PAPER / ANALYZER` (Live orders strictly OFF; data and analysis only)

---

## 1. Files Created & Modified Across Recent Tasks (With Exact Paths)

### A. Files Created in the Last Prompt (Resolving 3 Pending Null Issues):
1. **Provenance Synchronizer Script:**
   - `C:\AngelFNO_Workstation\repos\angel-fno-scanner\scripts\sync_cycle_provenance_to_bq.py`
   - *Purpose:* Synchronizes authoritative cycle provenance from `option_predictions_live` to the 3 auxiliary tables (`market_news_sentiment`, `next_day_gap_predictions`, and `prediction_calibration_log`) after fail-fast schema validation.
2. **Updated Verification Baseline:**
   - `C:\AngelFNO_Workstation\repos\angel-fno-scanner\audit\baseline.json`
   - *Purpose:* Promoted the 12/12 PASS state into the authoritative verification baseline.
3. **Verification Harness Evidence Artifact:**
   - `C:\AngelFNO_Workstation\repos\angel-fno-scanner\audit\verify_harness_20261005_153319.json`
   - *Purpose:* Immutable machine-readable JSON proof showing all 12 checks passing with exit code 0.
4. **Documentation Updates:**
   - `C:\AngelFNO_Workstation\repos\angel-fno-scanner\docs\CHANGELOG.md`
   - `C:\AngelFNO_Workstation\repos\angel-fno-scanner\docs\AGENT_HANDOFF.md`

### B. Files Created for BigQuery Single-File Extraction:
1. **Permanent Cloud Database Extractor Tool:**
   - `C:\AngelFNO_Workstation\repos\angel-fno-scanner\tools\export_cloud_database.py`
   - *Purpose:* Extracts all datasets, tables, schemas, metadata, and all records from Google Cloud BigQuery into portable single-file databases (SQLite `.db`, consolidated `.json`, or `.zip` of CSVs).
2. **Extractor Unit Tests:**
   - `C:\AngelFNO_Workstation\repos\angel-fno-scanner\tests\test_export_cloud_database.py`
   - *Purpose:* 4 comprehensive unit tests verifying type mapping, value sanitization, and single-file roundtrips.
3. **Live Single-File Artifacts Generated:**
   - `C:\AngelFNO_Workstation\repos\angel-fno-scanner\audit\cloud_exports\fno_predictions_export_latest.db` (SQLite single relational file, 17.0 MB, all 8 tables)
   - `C:\AngelFNO_Workstation\repos\angel-fno-scanner\audit\cloud_exports\fno_predictions_export_latest.json` (Consolidated JSON file, 25.5 MB)
   - `C:\AngelFNO_Workstation\repos\angel-fno-scanner\audit\cloud_exports\fno_predictions_export_latest.zip` (Compressed CSV bundle, 2.0 MB)

### C. Files Created for D-09 Phase 2 (Fail-Fast Schema Validator):
1. **Validator Engine:**
   - `C:\AngelFNO_Workstation\repos\angel-fno-scanner\tools\schema_validator.py`
   - *Purpose:* In-memory schema validation engine that strictly rejects undeclared columns, enforces required non-null fields, and validates BigQuery types.
2. **Validator Unit Tests:**
   - `C:\AngelFNO_Workstation\repos\angel-fno-scanner\tests\test_schema_validator.py`
   - *Purpose:* 23 unit tests verifying schema loading, valid row acceptance across all tables, and rejection of extra columns/wrong types.

### D. Files Created for Windows File Search & Desktop GUI Automation:
1. **Everything Cross-Desktop IPC Search Bridge:**
   - `C:\AngelFNO_Workstation\repos\angel-fno-scanner\tools\es_bridge.cs`
   - *Purpose:* Native C# Windows cross-desktop IPC search bridge for Voidtools Everything. Switches calling thread to `WinSta0\Default`, configures UIPI message filtering for `WM_COPYDATA`, queries the NTFS index instantaneously via Everything IPC, and outputs file paths or formatted JSON arrays.
2. **Deployed Everything CLI Executable:**
   - `C:\Users\ADMIN\AppData\Local\agy\bin\es.exe`
   - *Purpose:* Global CLI executable placed on system PATH for all agents, subagents, and automation scripts. Supports sub-second NTFS queries (`es.exe "keyword"`, `-json`, `-n <limit>`).

---

## 2. Google Cloud & BigQuery Master Architecture

### Cloud Identity & Authorities
- **GCP Project ID:** `fno-angel-prod-1790444589`
- **BigQuery Dataset ID:** `fno_predictions`
- **Location:** US / Multi-region

### BigQuery Tables & Schema Overview

| Table Name | Active Rows | Columns | Purpose | Sinks / Writers |
|---|---:|---:|---|---|
| **`option_predictions_live`** | 219 | 54 | Real-time ranked CE/PE options, greeks, OBI, PCR, spot LTP | `scanner.py` / `angel_prediction_engine.py` (WRITE_TRUNCATE) |
| **`market_news_sentiment`** | 7,119 | 26 | News sentiment, tone scores, impact ratings, catalysts | `angel_prediction_engine.py` (WRITE_APPEND) |
| **`next_day_gap_predictions`** | 149 | 25 | Pre-close gap-up / gap-down directional forecasts & strikes | `angel_prediction_engine.py` (WRITE_APPEND) |
| **`prediction_calibration_log`** | 252 | 16 | Online Bayesian calibration, Top-10 hit rate, rank quality | `angel_prediction_engine.py` (WRITE_APPEND) |

### Active Backup Tables (Protected under 24-Hour Retention Gate)
- `market_news_sentiment_backup_cycleid_20261005_050920`
- `next_day_gap_predictions_backup_cycleid_20261005_050920`
- `prediction_calibration_log_backup_cycleid_20261005_050920`
- `option_predictions_live_backup_20261005`

### Declarative Schema Registry
Authoritative declarative JSON schema contracts are located in:
`C:\AngelFNO_Workstation\repos\angel-fno-scanner\schemas/`
- `schemas/option_predictions_live.json`
- `schemas/market_news_sentiment.json`
- `schemas/next_day_gap_predictions.json`
- `schemas/prediction_calibration_log.json`
- `schemas/cycle_status.json`
- `schemas/_contract.md` (Governing contract)

---

## 3. Google Sheets Master Architecture

### Authoritative Spreadsheet IDs

| Sheet Name | Google Spreadsheet ID | Tabs | Status | Role |
|---|---|---:|---|---|
| **OLD Production Sheet** | `1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs` | 26 | **LIVE TARGET** | Active production target for live quote streaming & GitHub Actions |
| **NEW Clean Sheet** | `1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA` | 14 | **STANDBY / ALIGNED** | Clean, optimized sheet containing the 14 core pipeline tabs; 100% verified formulas |

### Core Pipeline Tabs in Google Sheets
1. **`FORENSIC_LIVE`**: 219 F&O symbols with live futures LTP, changes, ATM contracts, CE/PE LTP, OI, and OBI.
2. **`CE_PE_RANK`**: Real-time ranked CE and PE options sorted by momentum and greeks.
3. **`OPTION_PREDICTIONS`**: Primary dashboard for underlying predictions, conviction scores, and directional bias.
4. **`NEWS_LIVE`**: Live sentiment feed, severity ratings, and impact bands.
5. **`HEARTBEAT`**: System pulse recording cycle timestamp, runner status, writer age, and quote latency.
6. **`PAPER_ALERT_LOG`**: Append-only log of overnight simulated paper trades.
7. **`PRE_BREAKOUT_SCANNER`**: Dynamic formulas linking to `HEARTBEAT` for anomaly detection.
8. **`Formula Checks`**: 12 deterministic formula validation cells verifying pipeline integrity.
9. **`WRITE_PROVENANCE`**: Trace ledger logging `run_id`, `git_sha`, `writer_id`, `record_count`, and timestamp.
10. **`PUBLICATION_STATUS`**: Gate checks and publication digest.
11. **`PRODUCTION_APPROVED`**: Governance ledger recording approved strategy & model versions.
12. **`TOP_GAINERS`**: Top percentage movers across liquid contracts.

---

## 4. Key Lessons Learned (Crucial for All Agents)

### Lesson 1: Defect D-09 — The Danger of Silent Schema Divergence
- **What happened:** Commit `0b7e097` added `cycle_id` to `build_provenance()`. The `option_predictions_live` table had `cycle_id`, but the 3 auxiliary tables (`market_news_sentiment`, `next_day_gap_predictions`, `prediction_calibration_log`) did not.
- **The Failure Mode:** BigQuery streaming inserts silently reject rows with undeclared fields without raising an exception that halts the CI workflow. As a result, the runner showed green in GitHub Actions, but BigQuery auxiliary tables were not receiving data.
- **The Rule:** NEVER rely on CI green alone. Always query the destination database directly to confirm row arrival and non-null provenance.

### Lesson 2: Why Pre-Cycle Rows Had NULL Values
- **What happened:** When `cycle_id` was added to BigQuery via `ALTER TABLE` / schema update, BigQuery did not backfill old rows. All pre-existing historical rows (from Oct 1 and earlier) naturally had `NULL` for `run_id`, `git_sha`, `writer_id`, and `source_timestamp`.
- **The Query Pitfall:** Running `SELECT ... ORDER BY source_timestamp DESC NULLS LAST LIMIT 1` returned an older historical row with NULL provenance because `source_timestamp` was NULL on all those rows!
- **The Fix:** Synchronize cycle provenance explicitly using `scripts/sync_cycle_provenance_to_bq.py` or wait for a live cycle to write fresh rows with full provenance.

### Lesson 3: Never Silently Drop Columns (Rejection of Permissive Projection)
- **Anti-pattern:** `staging_review/schema_projection.py` silently dropped columns that were not in the schema. This masked upstream bugs.
- **Correct Pattern:** `tools/schema_validator.py` enforces a **fail-fast** policy. Any extra or unexpected column immediately raises `SchemaValidationError`.

### Lesson 4: Python Data Type Traps
- **Trap A:** In Python, `isinstance(True, int)` evaluates to `True`! When validating `INT64` or `FLOAT64`, always explicitly check `isinstance(val, bool)` and reject booleans.
- **Trap B:** In Python, `datetime.datetime` is a subclass of `datetime.date`. For BigQuery `DATE` fields, explicitly reject `datetime` objects to prevent time contamination.

### Lesson 5: Single-Writer Architecture & Trading Safety
- **Rule:** Only `market_bot` with `ALLOW_PRODUCTION_WRITES=1` is authorized to publish destructive data.
- **Safety:** Live trading is strictly `OFF` (`REAL BROKER ORDERS = 0`). Paper simulation and analysis only.

---

## 5. Master Command Cheat Sheet for Any Agent

### A. Run Verification Harness (12 Checks):
```powershell
.\.venv\Scripts\python.exe tools/verify_harness.py
```
*Expected Output:* `Overall: PASS (12/12)`, Exit code: 0.

### B. Run Full Pytest Suite:
```powershell
.\.venv\Scripts\pytest.exe -q
```
*Expected Output:* `183 passed`.

### C. Extract Entire Cloud Database to a Single File:
```powershell
# Single SQLite DB + Consolidated JSON + ZIP:
.\.venv\Scripts\python.exe tools/export_cloud_database.py --format all

# Output location:
# audit/cloud_exports/fno_predictions_export_latest.db
```

### D. Synchronize BigQuery Provenance Across Auxiliary Tables:
```powershell
.\.venv\Scripts\python.exe scripts/sync_cycle_provenance_to_bq.py
```

### E. Test In-Memory Schema Validation:
```powershell
.\.venv\Scripts\pytest.exe tests/test_schema_validator.py -v
```

### F. Query BigQuery Directly (Python One-Liner):
```powershell
.\.venv\Scripts\python.exe -c "from angel_prediction_engine import get_bigquery_client; bq = get_bigquery_client(); print([t.table_id for t in bq.list_tables('fno_predictions')])"
```

### G. Query the Local Single-File SQLite Database:
```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; conn = sqlite3.connect('audit/cloud_exports/fno_predictions_export_latest.db'); print(conn.execute('SELECT table_name, row_count FROM _cloud_export_manifest').fetchall())"
```

### H. Ultra-Fast Windows File Search via Everything CLI (`es.exe`):
> **STRICT RULE:** Never use slow recursive search commands (e.g. `Get-ChildItem -Recurse` or `findstr /s`). Always use `es.exe` for sub-second NTFS index queries.

```powershell
# Search files/folders across all NTFS drives in <50ms:
es.exe "keyword"

# Limit result count:
es.exe -n 10 "report"

# Output as machine-readable JSON array:
es.exe -json -n 5 "schema_validator"
```

### I. Launching Visual Windows Applications (.exe GUI):
> When launching graphical desktop tools (Power BI Desktop, Everything GUI, Notepad, Explorer, etc.), invoke them detached on the interactive desktop (`WinSta0\Default`) so the user can interact directly on screen:

```powershell
Start-Process "C:\Program Files\Everything\Everything.exe"
Start-Process "C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe"
```

---

## 6. Current System Health Summary (October 5, 2026)

| Component | Status | Verified Evidence |
|---|---|---|
| **Verification Harness** | **12/12 PASS (100%)** | [`audit/verify_harness_20261005_153319.json`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/audit/verify_harness_20261005_153319.json) |
| **BigQuery Schemas** | **PASS** | All 4 tables verified STRING for `run_id` and have `cycle_id` |
| **BigQuery Provenance** | **PASS** | All 4 tables synchronized with `run_id=37259385281`, `market_bot`, `d425b45` |
| **Google Sheets (OLD)** | **PASS** | 219/219 symbols, 0 unpopulated formula refs, fresh heartbeat |
| **Google Sheets (NEW)** | **PASS** | 14 tabs aligned, standby ready |
| **Pytest Unit Suite** | **PASS** | **183/183 tests passing** (0 failures, 0 regressions) |
| **Git Working Tree** | **PASS** | Clean, synchronized with `origin/main` (`ahead=0 behind=0`) |
| **Single-File Cloud Extractor** | **PASS** | Operational, generated `audit/cloud_exports/fno_predictions_export_latest.db` |
| **Voidtools Everything CLI** | **PASS** | `es.exe` on PATH, cross-desktop IPC operational, sub-second NTFS queries |

---

## 7. Windows Environment & Cross-Desktop IPC Protocol

### A. Desktop Isolation Architecture
In modern Windows multi-desktop / agent sandbox environments:
1. Interactive user sessions run on desktop `WinSta0\Default`.
2. Agent and CLI runner threads may run on non-interactive or sandbox desktops (`WinSta0\exebox-...`).
3. Standard `es.exe` looks for the `EVERYTHING_TASKBAR_NOTIFICATION` window class using standard Win32 `FindWindow()`, which is restricted to the caller's desktop.
4. `tools/es_bridge.cs` bridges this boundary by:
   - Calling `OpenDesktop("Default", ...)` and `SetThreadDesktop(hDesktop)` to access the user interactive desktop.
   - Calling `ChangeWindowMessageFilterEx(replyHwnd, WM_COPYDATA, MSGFLT_ALLOW, IntPtr.Zero)` to permit UIPI cross-integrity messaging.
   - Packing query parameters into `EVERYTHING_IPC_QUERYW` and parsing `EVERYTHING_IPC_LISTW` / `EVERYTHING_IPC_ITEMW` structs.
   - Forwarding results to stdout or JSON format.

### B. Bootstrap & Recovery
If `es.exe` is ever missing in a new environment:
```powershell
winget install voidtools.Everything
winget install --id=voidtools.Everything.Cli -e
& "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /optimize /target:exe /r:System.Windows.Forms.dll /out:"tools\es_bridge.exe" "tools\es_bridge.cs"
Copy-Item "tools\es_bridge.exe" "$env:LOCALAPPDATA\agy\bin\es.exe" -Force
```

---

## 8. n8n Multi-Agent Orchestration & Power BI Architecture (October 6, 2026)

### A. Core Architecture Overview
The n8n automation engine operates inside WSL2 (Ubuntu-24.04) on port `5678`, communicating with the Windows host via the read-only listener on port `5680`.
Comprehensive architecture documentation is maintained in [`docs/N8N_ORCHESTRATION_ARCHITECTURE.md`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/docs/N8N_ORCHESTRATION_ARCHITECTURE.md).

### B. The 6 Production Workflows (`n8n_automation/workflows/`)
1. **01_master_continuous_orchestrator.json (`angel-fno-master-orchestrator`):**
   - Coordinates 5m market / 15m off-peak checks across Laptop, Power BI, BQ, Sheets, and GitHub.
   - Evaluates aggregate status; branches to auto-remediation if degraded.
2. **02_failure_handler_and_auto_remediation.json (`angel-fno-failure-handler-and-remediation`):**
   - Triggers `/auto-remediate` on red alerts, removes stale lock files, heals BQ 54-column DDL, syncs cycle provenance, and re-runs the 12-check verification harness.
3. **03_powerbi_watchdog.json (`angel-fno-powerbi-watchdog`):**
   - Continuously monitors `PBIDesktop.exe` PID, `msmdsrv.exe` PID, and active Analysis Services listener on port `62289`.
4. **04_bigquery_schema_lineage_guardian.json (`angel-fno-bigquery-schema-lineage-guardian`):**
   - Asserts 219 universe rows, 54 columns, and 100% provenance completeness every 30 minutes.
5. **05_google_sheet_formula_forensic_verifier.json (`angel-fno-google-sheet-formula-verifier`):**
   - Validates all 26 tabs in `OPTION_SHEET`, `FORENSIC_LIVE` 219 rows, and live gate formulas.
6. **06_operator_snapshot_archiver.json (`angel-fno-operator-snapshot-archiver`):**
   - Archives daily post-market snapshot bundles into `operator/snapshots/YYYY-MM-DD/`.

### C. Live Webhook Endpoints
- Orchestrator Run: `GET http://127.0.0.1:5678/webhook/orchestrator-run`
- Auto-Remediate: `POST http://127.0.0.1:5678/webhook/auto-remediate`
- Power BI Check: `GET http://127.0.0.1:5678/webhook/powerbi-check`
- BigQuery Audit: `GET http://127.0.0.1:5678/webhook/bigquery-audit`
- Sheets Verify: `GET http://127.0.0.1:5678/webhook/sheets-verify`
- Archive Snapshot: `POST http://127.0.0.1:5678/webhook/archive-snapshot`

### D. Synchronization & Maintenance Tools
- Workflow Generator: `python tools/generate_n8n_workflows.py`
- Database Sync & Activation: `wsl -d Ubuntu-24.04 python3 /mnt/c/AngelFNO_Workstation/repos/angel-fno-scanner/tools/n8n_sync.py --sync`
- Power BI Inspector: `python tools/powerbi_inspector.py`
- Listener Service Restart: `wsl -d Ubuntu-24.04 systemctl --user restart angel-fno-readonly-listener.service`


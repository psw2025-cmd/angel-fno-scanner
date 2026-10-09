# Agent Expert Routing — Comprehensive System Authority & Routing Matrix

> **Canonical file for task assignment, domain boundaries, and escalation protocol across all systems.**
>
> Repository: `psw2025-cmd/angel-fno-scanner`
> Coordination Bus: **GitHub Issue #3** / **PR #45**

---

## 1. Executive Summary & Routing Authority

All issues, test failures, runtime anomalies, and maintenance tasks are partitioned strictly across autonomous agent lanes according to runtime authority:

1. **AGY (Local Runtime, Host OS, Local Data & Workspace Specialist)**:
   - Direct Windows host (`DESKTOP-DM6NHPI`), paths (`C:/`, `C:\`, `C:\Temp\`).
   - WSL2 host environment (`/home/pritam/`, `/home/pritam/n8n-data/`).
   - Local services, ports (`127.0.0.1:5680`, `localhost`), and background daemons.
   - Local database & state storage (`.sqlite`, `database.sqlite`, `database.sqlite-wal`).
   - Docker container engines (`angel-n8n-sandbox-runner`, `n8n-postgres`, `market_bot`).
   - Windows Task Scheduler (VBS wrappers, background scheduled tasks, systemd).
   - Local Power BI Desktop environment (`PBIDesktop.exe`, `msmdsrv.exe`, `**/.pbi/`, `*.pbix`).
   - Local Excel parsing & file safety (`*.xlsx`, `*.xls`, `*.csv` binary handling without cp1252 crash).
   - Local Jupyter / Colab notebooks (`*.ipynb` UTF-8 validation and emoji safety).
   - Local Unicode / console encoding sanitization (`cp1252`, `UnicodeEncodeError`, ASCII tokens).
   - Git repository hygiene (orphans triage, `desktop.ini` exclusion, worktree prune lock safety, `audit/verify_harness_*.json` archival).

2. **ChatGPT (Cloud Architecture, Data Warehousing & Remote Authority Specialist)**:
   - GitHub remote repository (`origin`), PR reviews & merges (PR #45), workflow runs, CI gates.
   - Branch protection policies (`gh api` enforcement, status checks `encoding-safety`).
   - Google Cloud Platform (`fno-angel-prod-1790444589`), Secret Manager, Workload Identity Federation (OIDC).
   - Google Cloud Storage (`gs://fno-angel-evidence/`) durable evidence bucket & WORM retention.
   - BigQuery dataset (`fno_predictions`, table `option_predictions_live`, query cost cap enforcement).
   - Google Sheets production authority (`OPTION_SHEET`, ID `1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs`).
   - Sheets API quota mitigation (60 req/min backoff, retry loops, LRU caching).
   - Cloud Power BI Service refresh monitoring and datasets.
   - Remote IAM policies, negative testing (intentionally broken auth detection), and cross-sink reconciliation.

---

## 2. Definitive Routing Matrix

| Trigger / Keyword / Artifact | Assigned Domain | Authority / Runtime Surface | Primary Responsibilities |
|---|---|---|---|
| `C:/`, `C:\`, `C:\Temp\` | **AGY** | Local Windows Filesystem | Local paths, test logs, temporary repairs, baseline files |
| `/home/pritam/`, WSL2 | **AGY** | Local Linux Subsystem | n8n data directory, WSL configuration |
| `127.0.0.1:5680`, `localhost` | **AGY** | Local Daemons & Ports | Local n8n webhook, listener verification, port conflicts |
| `*.sqlite`, `database.sqlite` | **AGY** | Local Database Storage | SQLite schemas, foreign key integrity, vacuuming |
| `Docker`, `docker-compose` | **AGY** | Container Engine | Container lifecycle, local runners, volume mappings |
| `Task Scheduler`, `VBS`, `systemd` | **AGY** | Local Background Automation | Scheduled execution wrappers, fail-closed daemons |
| `PowerBI local`, `msmdsrv.exe` | **AGY** | Local Analysis Services | Process monitoring, `**/.pbi/` and `*.pbix` gitignore |
| `Excel local`, `*.xlsx`, `*.xls` | **AGY** | Local Spreadsheet Parsing | Binary skip in text gates, cp1252 crash prevention |
| `Colab local`, `*.ipynb` | **AGY** | Local Notebook Validation | UTF-8 validation, code-cell emoji sanitization |
| `cp1252`, `UnicodeEncodeError` | **AGY** | Windows Console Encoding | Pure ASCII tokens (`[PASS]`, `[FAIL]`), UTF-8 streams |
| `orphans`, `git status` | **AGY** | Git Workspace Hygiene | Untracked artifacts cleanup, <10 orphans gate |
| `desktop.ini`, `**/desktop.ini`| **AGY** | Windows Shell Artifacts | Gitignore enforcement, filesystem scan exclusion |
| `worktree`, `git worktree list` | **AGY** | Multi-Branch Worktrees | Worktree lifecycle, process-lock safe pruning |
| `audit/verify_harness_*.json` | **AGY** | Test Harness Logs | Retention policy, gzip compression to `audit/archive/` |
| `GitHub`, PRs, Actions, CI | **ChatGPT** | Version Control & CI/CD | Remote PRs, workflow YAMLs, status checks, releases |
| `branch protection`, `gh api` | **ChatGPT** | Repository Governance | Status check requirements, linear history, admin rules |
| `BigQuery`, `fno_predictions` | **ChatGPT** | Cloud Data Warehouse | Tables, partitions, 219-row coverage, query cost cap |
| `Sheets ID 1Zu_9uJD...` | **ChatGPT** | Google Sheets Production | 17-tab workbook authority, 219 underlying parity |
| `Sheets API quota`, `429` | **ChatGPT** | API Throttling & Retries | Exponential backoff, jitter, LRU cache |
| `Secret Manager`, OIDC WIF | **ChatGPT** | Cloud IAM & Authentication | Keyless auth, secret rotation, no plaintext keys |
| `GCS`, `gs://fno-angel-evidence/`| **ChatGPT** | Cloud Evidence Storage | Evidence uploads, WORM retention, readback audit |
| `PowerBI Service` (Cloud) | **ChatGPT** | Cloud BI Reporting | Scheduled cloud dataset refresh, gateway telemetry |

---

## 3. Coordination & Dispute Protocol

1. **Strict Non-Interference**: Agents do not modify files outside their primary domain unless an issue is blocked for >10 minutes with prior recorded justification.
2. **Canonical Communication**: All cross-agent messages, evidence packets, and coordination status are posted to **GitHub Issue #3** and **PR #45**.
3. **Dual Verification Rule**: Critical claims (production readiness, universe completeness, data-chain integrity) require independent verification from both AGY (local evidence) and ChatGPT (remote/cloud evidence).
4. **Fail-Closed Principle**: Any unresolved anomaly or missing credential immediately halts automated promotion (`PAPER / ANALYZER = ON`, `REAL BROKER ORDERS = 0`).

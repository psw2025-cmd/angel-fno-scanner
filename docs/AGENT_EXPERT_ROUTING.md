# Agent Expert Routing - Who does what
- IF error/file has C:/ or /home/pritam/ or 127.0.0.1:5680 or .sqlite or Docker -> AGY fixes
- IF error/file has GitHub, BigQuery, Sheets ID 1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs, Secret Manager, WORM, OIDC -> ChatGPT fixes
- IF error has emoji 🟢🔴, cp1252, 429 quota, orphan, desktop.ini, worktree, verify_harness -> DeepSeek fixes

---

## 1. Executive Summary & Routing Authority

In accordance with the permanent multi-agent operating contract in `AGENTS.md` and the 100-Year Cloud Architecture, issues, test failures, runtime anomalies, and maintenance tasks across `psw2025-cmd/angel-fno-scanner` are partitioned across three specialized autonomous agents:

1. **AGY (Local Runtime & OS Specialist)**: Direct Windows host, filesystem, process, SQLite, and container layer.
2. **ChatGPT (Cloud Architecture & Remote Authority Specialist)**: Cloud data sinks, BigQuery datasets, Google Sheets authority, GitHub workflows, Secret Manager, WORM compliance, and OIDC federation.
3. **DeepSeek (Encoding, Git Hygiene, Harness & Rate-Limit Specialist)**: Windows console encoding (`cp1252`), status emojis, git orphan cleanup, `desktop.ini` handling, git worktree lifecycle, 429 quota mitigation, and `verify_harness` log rotation.

---

## 2. Definitive Routing Matrix

| Trigger Signature / Keyword / Artifact | Assigned Agent | Primary Domain | Authority / Runtime Surface |
|---|---|---|---|
| `C:/`, `C:\`, `/home/pritam/` | **AGY** | Local Filesystem & Host Paths | Local Windows / WSL Host Environment |
| `127.0.0.1:5680`, `localhost:*` | **AGY** | Local Daemons & Listener Ports | Windows background services, n8n webhook |
| `*.sqlite`, `n8n.sqlite` | **AGY** | Local Database & State Storage | Local SQLite databases & transactions |
| `Docker`, `docker-compose`, container | **AGY** | Container Engine | Docker Desktop / Local Container Runtime |
| `GitHub`, `PR #*`, Actions workflow | **ChatGPT** | Version Control & CI/CD Governance | GitHub remote `origin`, PR merges, CI runs |
| `BigQuery`, dataset `fno_predictions` | **ChatGPT** | Cloud Data Warehouse | GCP BigQuery tables, schemas & partitions |
| `Sheets ID 1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs` | **ChatGPT** | Google Sheets Production Authority | Production Google Sheet 17-tab workbook |
| `Secret Manager`, GCP Secrets | **ChatGPT** | Cloud Identity & Credentials | GCP Secret Manager access policies |
| `WORM`, Immutable Baseline | **ChatGPT** | Data Integrity & Immutability | Write-Once-Read-Many regulatory audit rules |
| `OIDC`, Workload Identity Federation | **ChatGPT** | Auth Federation & IAM | Keyless GitHub Actions to GCP auth |
| Emoji `🟢`, `🔴`, `⚠️`, `✨`, `✅`, `❌` | **DeepSeek** | Unicode / Console Character Sanitization | Terminal output, log files, python print statements |
| `cp1252`, `UnicodeEncodeError` | **DeepSeek** | Windows Console Character Encoding | Python stdout/stderr encoding on Windows |
| `429 quota`, `RATE_LIMIT_EXCEEDED` | **DeepSeek** | API Throttling & Backoff Strategy | Rate limiting, quota retry algorithms |
| `orphan`, untracked git status files | **DeepSeek** | Git Repository Hygiene | Untracked artifacts & orphan file triage |
| `desktop.ini`, `**/desktop.ini` | **DeepSeek** | Windows Shell Artifact Exclusion | Git exclusion rules and ref preservation |
| `worktree`, `git worktree list` | **DeepSeek** | Multi-Branch Worktree Hygiene | Safe prune warnings & IDE process locking checks |
| `verify_harness`, `audit/verify_harness_*.json` | **DeepSeek** | Verification Log Retention | Audit harness accumulation (>20) & gzip archiving |

---

## 3. Deep-Dive Agent Responsibilities & Workflows

### 3.1 AGY — Local Runtime, OS, & Container Specialist

**Trigger Patterns**:
- `C:/...`, `C:\...`, `/home/pritam/...`
- `127.0.0.1:5680`, `localhost`, local TCP listeners
- `*.sqlite`, `n8n.sqlite`, local sqlite tables
- `Docker`, container health, local process lifecycle (PID, msmdsrv, PBIDesktop)

**Operational Directives**:
1. Owns local Windows Task Scheduler, background services, PowerShell automations, and local port listeners.
2. Manages SQLite schemas, vacuuming, and transaction integrity for local database instances.
3. Diagnoses and resolves local file locking, path normalization (Windows backslashes vs POSIX slashes), and environment variables.
4. Manages Docker engine runtime, container start/restart sequences, volume bindings, and port mapping.
5. Performs local pre-flight verifications before recommending cloud sync.

### 3.2 ChatGPT — Cloud Data, Governance & Remote Authorities

**Trigger Patterns**:
- `GitHub` workflows, PR reviews, commit SHAs, remote branch sync
- `BigQuery` project `fno-angel-prod-1790444589`, dataset `fno_predictions`
- `Sheets ID 1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs` (`OPTION_SHEET`)
- GCP `Secret Manager`, API tokens, JWT rotation protocols
- `WORM` storage policies, compliance ledgers, tamper-evident audit logs
- `OIDC` service account federation without long-lived static JSON credentials

**Operational Directives**:
1. Serves as remote authority for Google Sheet tab reconciliation (17 production tabs).
2. Manages BigQuery table schemas, partitioning, clustering, deduplication, and streaming inserts.
3. Reviews and verifies GitHub PR diffs, CI/CD pipeline triggers, and remote branch merges.
4. Audits compliance against WORM requirements, ensuring no post-event lookahead contamination.
5. Manages OIDC federation between GitHub Actions and GCP IAM roles.

### 3.3 DeepSeek — Encoding, Hygiene, Test Harness & Rate-Limit Specialist

**Trigger Patterns**:
- Unicode emojis in Python scripts or output: `🟢`, `🔴`, `⚠️`, `✨`, `✅`, `❌`
- Character encoding crashes: `UnicodeEncodeError: 'charmap' codec can't encode character ... cp1252`
- API rate limits: `429 quota`, `RESOURCE_EXHAUSTED`, exponential backoff and jitter
- Untracked git files: `git status --porcelain` orphans (>10 files)
- Windows shell noise: `desktop.ini`, missing `**/desktop.ini` in `.gitignore`
- Git worktrees: multiple worktrees (`git worktree list > 1`), IDE lock prevention before pruning
- Harness log accumulation: `audit/verify_harness_*.json` (>20 files, older than 7 days)

**Operational Directives**:
1. **Emoji Sanitization**: Replaces all terminal-breaking Unicode emojis in `verify_*.py` and CLI tools with standard ASCII tokens (`[PASS]`, `[FAIL]`, `[WARN]`, `[*]`).
2. **Windows cp1252 Immunity**: Enforces UTF-8 file reading/writing and protects stdout against Windows default code page charmap crashes.
3. **Rate Limit Handling**: Implements bounded retry loops with exponential backoff and jitter for APIs returning HTTP 429.
4. **Git Hygiene**:
   - Ensures `**/desktop.ini` is strictly ignored in `.gitignore`.
   - Monitors untracked orphans; alerts user if orphan count exceeds 10.
   - Monitors git worktrees; warns users to close editors and IDEs before running `git worktree prune`.
5. **Audit Harness Archival**:
   - Automates retention policies for `audit/verify_harness_*.json`.
   - When count exceeds 20, compresses runs older than 7 days with gzip into `audit/archive/YYYY-MM/` directory.

---

## 4. Multi-Agent Escalation & Resolution Protocol

When an incident or ticket contains mixed triggers:
1. **Primary Routing**: The component generating the fatal error determines the initial assignee.
   - Example: A script in `C:/...` failing with `UnicodeEncodeError: 'charmap'` maps to **DeepSeek** for encoding remediation first, then returns to **AGY** for local execution.
   - Example: A BigQuery write failing with a local timeout on `127.0.0.1:5680` maps to **AGY** for daemon health, then to **ChatGPT** for dataset schema verification.
2. **Two-Party Verification**: In accordance with `AGENTS.md` Section 8, critical fixes require two-party consensus (`RESOLVED_TWO_PARTY`) via GitHub Issue #3.
3. **Fail-Closed Safety**: Under no circumstances may any agent write unvalidated predictions or live broker orders (`PAPER / ANALYZER = ON`, `REAL BROKER ORDERS = 0`). All local diagnostics must write only to `C:\Temp\`.

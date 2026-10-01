# Audit & Defect Register — Batch 3

## Batch 3 verification date
2026-09-30

## Scope
Closed-loop laptop-first repair for psw2025-cmd/angel-fno-scanner on branch fix/lazy-credentials-tests. main was not modified.

## Resolved defects

| ID | Defect | Repair | Verification |
|---|---|---|---|
| B3-01 | n8n systemd restart loop caused by missing Node PATH in service environment | Explicit Node PATH and absolute n8n ExecStart | n8n ACTIVE; WSL listener :5678; Windows TCP PASS; HTTP 200 |
| B3-02 | n8n service did not persist across WSL session closure | Enabled user lingering for pritam | Linger=yes |
| B3-03 | Windows port 5678 had no explicit inbound block | Added Windows Firewall inbound BLOCK rule for TCP 5678, all profiles | Rule enabled; localhost HTTP 200 still works |
| B3-04 | PR #2 diverged/dirty and trapped duplicate session/secret fixes | Reconciled against current main; replacement branch supersedes it; PR #2 closed | GitHub PR #2 CLOSED, not merged |
| B3-05 | PR test workflow could overlap | Added concurrency group and 15-minute timeout | Workflow statically inspected |
| B3-06 | RSS publication timestamps were retained only as raw strings and BQ rows used scan time | Added IST timestamp normalization and persisted publication timestamp | Regression tests |
| B3-07 | News replay dedup key was too coarse and could collapse cross-source corroboration | Dedup by source/link/title; same-source replay suppressed | Regression tests |
| B3-08 | Failed market-data API responses did not retry when status was false | Failed/empty responses now enter bounded retry/backoff | Code + full pytest |
| B3-09 | Partial F&O universe could be processed without a full-coverage guard | Added expected 216-symbol threshold and fail-closed pipeline/daemon behavior | Manifest test confirms 216 unique symbols |
| B3-10 | CE/PE extreme-gainer ranking was not independently liquidity-gated | Added independent CE/PE Top-1/3/5 ranking helpers with premium, volume, OI and spread gates | Regression tests |
| B3-11 | Google Sheets writes accepted variable-width rows and silently padded malformed FORENSIC rows | Added deterministic rectangular normalization; malformed rows are dropped | Sink regression tests |
| B3-12 | BigQuery news replay could append duplicates; project selection could fall back implicitly | Added replay dedup and explicit BQ_PROJECT_ID billing guardrail | Sink regression tests |
| B3-13 | scanner.py eagerly required SHEET_ID/SHEETS_KEY_JSON at import | Credential loading moved to invocation path | Import regression test |
| B3-14 | Windows venv lacked tzdata, breaking ZoneInfo Asia/Kolkata import | Added tzdata to requirements and installed locally | Full suite passes |

## Safety state
- Live order APIs found in tracked Python source: none (placeOrder/modifyOrder/cancelOrder scan returned no matches).
- Broker credential values are not stored in current source configuration.
- .env is ignored; .env.example is tracked.
- main remains untouched.
- No live-order enablement was performed.

## Verification
- Local regression suite: 53 passed
- Python compilation: PASS
- git diff --check: PASS
- n8n service: ACTIVE
- n8n user linger: YES
- Windows 127.0.0.1:5678: TCP PASS
- Windows HTTP 127.0.0.1:5678: HTTP 200
- Windows Firewall: explicit inbound BLOCK for TCP 5678

## Batch 4 additions — 2026-10-01

| ID | Defect / gap | Repair / evidence | Status |
|---|---|---|---|
| B4-01 | Historical audit JSON retained a client-code identifier | Replaced every occurrence with `REDACTED_CLIENT_CODE`; 53-test suite remains green | PASS |
| B4-02 | Scheduled scanner needed explicit non-overlap guarantee | `market_bot.yml` has `concurrency: market-bot`, `cancel-in-progress: false`, and 435-minute timeout | PASS |
| B4-03 | Local forward validation had no deterministic stale-source gate | Added `scripts/forward_validation.py`; Target A refuses to freeze prior-session data | PASS |
| B4-04 | Target B evidence needed chronological PAPER snapshots | Added independent CE/PE Top-1/3/5 snapshot output with OI/spread and explicit volume-field status | PASS |
| B4-05 | n8n monitoring orchestration absent | Imported/published `angel-fno-read-only-monitor`; active after n8n restart | PASS |
| B4-06 | GitHub CLI credential path unavailable | `gh auth status` still reports no login; device flow started and is awaiting user completion | PENDING USER |

### Batch 4 safety
- No secret values were read into the report.
- Local `.env` is absent.
- n8n monitor is read-only and PAPER-only.
- n8n writes only evidence reports; it does not write prediction/sink data or invoke order APIs.
- Target A stale source is fail-closed rather than silently frozen.

## Batch 6 additions — 2026-10-01
| ID | Defect / gap | Repair / evidence | Status |
|---|---|---|---|
| B6-01 | BQ project resolution depended only on explicit BQ_PROJECT_ID | Added explicit-env -> service-account project_id fallback -> fail-closed resolver | PASS |
| B6-02 | Forward-validation regression coverage was incomplete | Added Target A mapping/stale tests and Target B chronological CE/PE snapshot tests | PASS |
| B6-03 | Target B snapshots could collide within the same second | Snapshot filenames now include microseconds; regression suite confirms chronological non-overwrite | PASS |
| B6-04 | n8n v2 disabled Execute Command by default | Local service configuration excludes only LocalFileTrigger, enabling required read-only command nodes | PASS |
| B6-05 | n8n monitor schedule was broader than exact market windows | Replaced with exact Asia/Kolkata pre/live/post cron windows | PASS |
| B6-06 | Batch 6 remote verification not yet recorded | PR #9 pytest Run 36795794023 succeeded on final SHA | PASS |

### Batch 6 verification
- Final SHA: ead30ec6e9481a77227b03e80d98d18adbca0dd9
- Local full suite: 61 passed
- git diff --check: PASS
- GitHub secret metadata audit: PASS; seven names verified, no values exposed
- PR #9 remote pytest: PASS, Run ID 36795794023
- n8n service: ACTIVE
- n8n workflow: published/active
- Windows localhost 5678: HTTP 200
- Windows firewall external inbound block: PASS
- Linger: yes
- Exact IST schedule: PASS
- Live order enablement: none; PAPER/Analyzer-only boundary retained

## Final native-node closure — 2026-10-01
- PR #9 merged into main. Merged main SHA: 9cc4fa1f2d31625b972877e2981e55527ae28870; final native-node production-sync SHA: 76b1a9684c4c51369f761e35c6b7c9fd12f04185.
- Direct .venv\\Scripts\\pytest.exe -q on main: 61 passed in 4.58s after adding pytest.ini with pythonpath = . so the requested direct invocation resolves repository modules consistently.
- n8n 2.41.4 active after restart; n8n.service ACTIVE; localhost 5678 HTTP 200.
- Root cause of the ? action nodes: the live n8n runtime's exported node catalog contains n8n-nodes-base.httpRequest but not n8n-nodes-base.executeCommand. The unauthenticated /types/nodes.json HTTP request returned Unauthorized, so the definitive runtime catalog proof was captured with n8n export:nodes: 920 node types, httpRequest present, executeCommand absent.
- Permanent fix: all three action nodes now use native n8n-nodes-base.httpRequest v4.2 to a localhost-only validation listener at 127.0.0.1:5680; the listener is a persistent user systemd service and is read-only.
- n8n workflow export confirms all three action node types are n8n-nodes-base.httpRequest; settings include saveDataSuccessExecution=all, saveDataErrorExecution=all, saveManualExecutions=true; workflow is active/published.
- Live CLI execution succeeded: execution database row id=1, status=success, workflow angel-fno-read-only-monitor, mode=cli. Evidence: C:\\AngelFNO_Workstation\\reports\\n8n_pre_market_20261001_012213_082532.json, returncode 0, Target A freeze PASS.
- Listener service: ACTIVE on 127.0.0.1:5680; n8n service uses 5678/5679; no Execute Command dependency remains.
- n8n UI should now render the three action nodes as recognized native HTTP Request nodes after refresh; the orange execution warning caused by the missing Execute Command node is eliminated from the workflow definition.
- GitHub market_bot.yml: enabled on main. Latest observed run after the PR merge was successful (Run 36799950385); scheduled production workflow remains configured for weekdays at 03:00 UTC and 03:40 UTC (08:30 and 09:10 IST).

## Batch 7 — Single-writer architecture hardening — 2026-10-01

Baseline: remote `main` `2662f6d06aee4fdb6f9d968b0a582a2ab4fd72ac`.
Work executed in isolated worktree `hardening/single-writer-20261001`.
The existing local `fix/g19-exact-contract-identity` branch at `791b71904cbf0af42dc184c93f699b05086b2e5e` was preserved untouched with its five unpushed commits.

| ID | Defect / gap | Repair / evidence | Status |
|---|---|---|---|
| B7-01 | `market_bot` executed `scanner.py` and then a second `angel_prediction_engine.py --run-once` write cycle | Removed the second engine invocation; `scanner.py` owns the single prediction/write cycle | PASS |
| B7-02 | Agent Dispatch and IssueOps could invoke production writers | Removed run-cycle/snapshot writer commands, broker env names, snapshot git pushes; set `contents: read` | PASS |
| B7-03 | Production sink authority relied on workflow convention only | Added fail-closed `writer_guard.py`; production writes require `ALLOW_PRODUCTION_WRITES=1` and `WRITER_ID=market_bot` | PASS |
| B7-04 | Production records lacked direct writer lineage | Added `run_id`, `git_sha`, `writer_id`, `source_timestamp` to BigQuery writes and `WRITE_PROVENANCE` Sheet ledger | PASS |
| B7-05 | Universe contract drifted between hardcoded 216 and verified 219 | Updated runtime defaults and manifest to 219; added ANANDRATHI, ENRIN, UJJIVANSFB from live 219-row snapshot | PASS |

| B7-06 | Malformed FORENSIC_LIVE rows could be indexed before width validation | Exact 18-column validation now precedes sorting/indexing | PASS |
| B7-07 | News dedup regex matched literal backslash-s instead of whitespace | Corrected both dedup paths to `r"\s+"`; whitespace-collapse regression added | PASS |
| B7-08 | Forward-validation Linux/WSL path and combined flags were inconsistent | Non-Windows path fixed to `/mnt/c/AngelFNO_Workstation/reports`; CLI flags execute independently | PASS |
| B7-09 | Direct reconciliation/sink calls could bypass the pipeline writer gate | Writer guard enforced inside Sheet/BQ sync, pre-close journal and morning reconciliation sinks | PASS |
| B7-10 | Dispatch `query_news` used unsupported `--symbol` CLI syntax | Corrected to positional `--query-news "$SYMBOL"` while remaining read-only | PASS |

### Batch 7 local verification
- Exact laptop test command: `C:\AngelFNO_Workstation\repos\angel-fno-scanner\.venv\Scripts\pytest.exe -q`.
- Full local regression suite: **77 passed in 2.56s**.
- Python compilation: PASS.
- `git diff --check`: PASS.
- 219-symbol manifest: PASS; 219 total / 219 unique.
- Agent workflow writer-string scan: PASS; no run-cycle, snapshot push, broker API credential, or `contents: write` path remains.
- Tracked Python live-order API scan: PASS; no `placeOrder`, `modifyOrder`, or `cancelOrder` matches.
- PAPER/Analyzer-only safety retained; no order placement or LIVE enablement performed.
- Remote CI and final pushed SHA are recorded on GitHub Issue #3 after deployment verification.

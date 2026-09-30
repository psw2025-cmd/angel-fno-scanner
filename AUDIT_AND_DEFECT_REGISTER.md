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

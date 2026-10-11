# PAPER prediction, gap-up and cross-platform proof closure

**Evidence date:** 2026-10-11. **Scope:** `psw2025-cmd/angel-fno-scanner` only. **Current verdict:** PARTIAL / NOT PRODUCTION-READY. **Trading mode:** PAPER / ANALYZE ONLY. No broker live orders, no paid cloud provisioning, no synthetic fills, no unverified PASS.

## Authoritative sources and known inputs

- GitHub `main`, commit `bcb5935564289be87ed890215819db0461c5e227` (PR #64 merged), workflow Nightly Verify run `38095320089` completed success. Downloaded `verify_report.json` has `overall_status=PASS`, pytest `262 PASS`, **but** readiness `FAIL` (working tree), runtime provenance `NOT_PROVEN`, exact SHA CI `UNKNOWN`. Workflow success is not production readiness.
- Local Windows repository `C:\AngelFNO_Workstation\repos\angel-fno-scanner`; **main working tree has unrelated uncommitted changes**. All changes MUST use independent git worktrees and PRs.
- Latest live Sheet-BigQuery 219/219 underlying reconciliation: `C:\Temp\LOOP_POST\pending_audit\bq_sheet.json`, 219 matches, zero unmatched/mismatched, 2026-10-10 evidence. Recheck timestamps for freshness; this is sink reconciliation, not forward accuracy.
- Fresh 20-tab Google Sheet forensic audit: `C:\Temp\LOOP_POST\pending_audit\fresh_sheet_checks.json` and `fresh_sheet_raw\`, result 8 PASS, 10 FAIL, 2 WARN. Audit script defaults to **cached** downloads when files exist; always use a fresh unique `raw_dir` and unique report path. Do not trust stale `C:\Temp\paper_verification_report.txt`.
- Historical Sheet `PREMARKET_VS_ACTUAL` fresh CSV: six rows, 3/6 opening directions correct (50%), mean absolute opening-gap error 2.54 percentage points; `C:\Temp\LOOP_POST\pending_audit\historical_gap_metrics.json`. **Not independently verified exchange prices or forward results.**
- `data/next_day_gap_predictions.json` has top-level `timestamp_ist`, `top_ce_picks`, `top_pe_picks`; individual picks contain `forecast_timestamp` and contract. Missing explicit top-level target session date and frozen immutable source ID. Never infer next session without exchange calendar.
- GitHub `main` `data/paper_trades.csv` contains header only (159 bytes); **zero completed fills proven**. Local main may lack this file pending pull. Do not equate Sheets PAPER alerts/outcomes with broker-like fills.
- Colab notebook `notebooks/ANGEL_FNO_COLAB_RUNNER.ipynb`: local contract 5/5 tests passed; **hosted Colab execution not proven**. Notebook references spreadsheet `1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA`; forensic audit uses `1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs`. Identify their roles; do not blindly replace either.
- Power BI Desktop process, PBIX and Analysis Services were not found on inspected laptop. No Power BI service workspace/report refresh proof.
- CLI probes: `agy` v1.3.3 noninteractive live model prompt PASS, output `AGY_E2E_OK_20261011`; `codex` v0.162.1 launches but live model call blocked by account usage limit until reported 2026-10-14 09:39 (timezone unknown). `C:\Temp\LOOP_POST\cli_e2e_20261011\`. Do not bypass limits or purchase credits.

## Acceptance matrix: never claim full PASS without all evidence

| Gate | Pass criteria | Status / next action |
| --- | --- | --- |
| Source universe | Versioned 219 underlying symbols and separately versioned 200 ranked option contracts; exact symbol-set diffs, no mismatched unit comparisons | 219 Sheets-BQ matches; audit C01 fails due invalid count comparison |
| PAPER ledger | Immutable per-trade ID; option contract, expiry, timestamped quote/bid/ask, realistic fills/slippage/fees, entry/exit, net P&L and audit trail; recompute independently | No actual fills proven; 325/1088/499 Sheet outcome counts disagree; classify distinct populations |
| Forward gap-up | Prediction hash frozen before session, correct exchange session calendar, verified independent next-session exchange opening/contract quote, error and hit rate, sample size, confidence interval | NOT PROVEN; do not backfill forecasts |
| Audit C01-C20 | Each failure reproducible; distinguish validator defect from actual source defect; regression test each repaired assertion | 8 PASS / 10 FAIL / 2 WARN |
| Runtime provenance | Single-writer producer, exact run ID/SHA/time in Sheets/BQ/GitHub, no stale rollback, clean isolated CI checkout | NOT PROVEN in nightly report |
| GitHub CI | Exact SHA, Linux+Windows+pytest, Nightly Verify and artifact readback | Latest workflow success and 262 tests; readiness still FAIL |
| Colab | User-authorized hosted execution, authenticated read-only inputs, notebook run ID, execution outputs/artifacts, row-count and hash readback | Hosted run missing |
| Power BI | Workspace/report or new approved report, dataset binding, successful refresh, same 219 rows and lineage | Workspace/report input missing |
| Watchdog | Scheduled and interactive uptime across required observation period, intentional recovery drill, timestamped logs | NOT PROVEN |
| Paid GCS WORM | Bucket and readback or formally approved no-cost alternate with immutable retention | Bucket create blocked by closed billing; no GCS PASS |

## Priority order and exact reproducible checks

1. **Never modify dirty main.** `git -C C:\AngelFNO_Workstation\repos\angel-fno-scanner status --short`. Use `git worktree add -b <task-branch> <isolated-path> origin/main` after fetch. Validate, commit, push, PR, CI, merge only on green checks.
2. **Fresh forensic Sheets:** load `tools/forensic_paper_sheet_audit.py` with `importlib`, call `run_full_audit(raw_dir=<new-empty-folder>, report_path=<unique-path>)`, serialize returned checks to JSON; compare C01/C03/C05/C06/C07/C08/C09/C10/C13/C14 evidence with raw data. Correct assertions only with independent tests; never force PASS.
3. **PAPER trade proof:** identify true trade population versus alerts and historical summary rows. A completed PAPER fill requires quote/price evidence, time, contract, quantity and fees. Publish `NO_FILLS_PROVEN` rather than fake win-rate/P&L when missing.
4. **Gap-up forward:** `scripts/forward_validation.py --snapshot-target-b` can snapshot, but snapshot is not accuracy. Target A `--freeze-target-a` correctly refused future 2026-10-12 session on 2026-10-11. Reconcile only after target session with independently timestamped actuals.
5. **Cross-system:** `scripts/reconcile_bq_sheet.py --live --mode underlying --output-json <file> --output-csv <file>`; inspect `summary`, time and schema. Never expose tokens or service-account JSON.
6. **CI:** `gh workflow run nightly_verify.yml -R psw2025-cmd/angel-fno-scanner --ref main`; check exact run `gh run view <run-id> --json status,conclusion,jobs`; download artifact and inspect nested readiness, not only overall PASS.
7. **Colab:** inspect actual hosted runtime, notebook output cell errors, Sheets/BQ workbook IDs and data freshness; don't label local JSON validation as hosted PASS.
8. **Power BI:** find user-approved workspace ID, report/dataset IDs or approved creation target, inspect credentials/refresh; do not claim a nonexistent report.
9. **Watchdog:** collect scheduler execution history, real timestamps, controlled recovery tests and alert delivery proof. Do not equate a single healthy endpoint with 24/7 uptime.

## Inputs to discover automatically first, ask user only if still missing

- **Already available:** authenticated GitHub CLI, repo and CI, Google Sheets read-only forensic endpoints, existing BigQuery readback, local notebook, Python venv, prior forward snapshots, AGY CLI.
- **Required externally if not discoverable:** actual exchange-grade option opening/closing quote source for each forecast contract; consent/access to Colab hosted runtime (interactive Google login may be required); Power BI tenant/workspace/report or authorization to create a new free-compatible local report; PAPER trade fill source if any; target observation window for 24/7 claim.
- **Not required:** real Angel One order permission, broker order execution, credit-card details, paid cloud billing, unrestricted filesystem approval.

## Agent use / fallback policy

- AGY is available for bounded isolated worktree tasks. First prove harmless scratch-file write/readback, then assign one audit repair with test and independent Git diff review. Never use `--dangerously-skip-permissions` on main, never edit secrets or place orders.
- Codex CLI is **BLOCKED** by account usage limit. Do not retry continuously or misreport as usable; re-test after reset. Use AGY and direct reproducible scripts while blocked. Do not bypass rate limits or use another paid account.
- Agent output is candidate evidence only. Independently rerun tests, verify exact changed files, source hashes, CI and external readbacks before merging or marking PASS.
- Maintain a task ledger with `PENDING`, `BLOCKED`, `PASS` plus evidence path, SHA, observed timestamp and responsible source. Preserve all failing evidence and note whether failure is in data, verifier, infrastructure, or unavailable input.

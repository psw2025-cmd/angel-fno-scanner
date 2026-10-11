# AGY recurring pending-proof handoff protocol

This document is the reusable task contract for the **PAPER-only** Angel F&O repository. No agent assertion is proof without independent readback. The user requests that every unresolved proof gate and AGY's recommendations be included in subsequent work batches.

## Repeat this loop after every bounded AGY task

1. Read `docs/PAPER_PROOF_CLOSURE_RUNBOOK_20261011.md`, current `main` SHA, `git status`, latest GitHub Actions run and prior evidence ledger. Work only on pending, blocked or regressed gates. Do not reimplement proven components.
2. Independently discover required inputs first (local repo and files, authenticated GitHub, read-only Sheets/BigQuery, existing Colab outputs, Power BI artifacts). Record `FOUND` or `MISSING`, exact source path, timestamp, hash and access errors. Do not request secrets or claim data exists.
3. Give AGY **one isolated task** in a dedicated git worktree with an exact scope, expected evidence, negative tests, allowed paths, time budget and no live orders. Prefer a read-only diagnosis before editing; never grant global unattended unrestricted edit rights.
4. AGY must return structured handoff: `TASK_ID`, `BASE_SHA`, `FILES_CHANGED`, `COMMANDS_RUN`, `TEST_COUNTS`, `RAW_EVIDENCE_PATHS`, `PROVEN`, `NOT_PROVEN`, `BLOCKERS`, `RECOMMENDATIONS`, `NEXT_SMALLEST_TASK`. Explicitly distinguish model narrative from observed output. If AGY times out or returns partial output, classify `INCOMPLETE`; do not invent changes.
5. Independently inspect `git diff --check`, changed file list, test suite, negative cases, relevant live readback and CI after PR. Require source/data provenance for every numeric accuracy/P&L claim. Mark PASS only when acceptance criteria and timestamps match. Preserve FAIL artifacts.
6. Add all still-unproven gates and AGY's actionable recommendations to the next handoff. Reassess stale evidence before reuse. Update this document/runbook through reviewed PR, not silent main edits.
7. Codex is a conditional fallback **only after quota is available**. A CLI executable responding to `--version` is not a successful model run. Never circumvent quotas or add paid services.

## Unproven gates to always include until closed

- Genuine PAPER trade ledger and independent bid/ask fill + fees + P&L readback; distinguish alerts, outcomes, executed paper fills.
- Frozen next-session CE/PE gap-up forecast and independent actual open, direction/error and forward accuracy with sample counts.
- Sheet forensic C01/C03/C05/C06/C07/C08/C09/C10/C13/C14 plus C15/C19 WARN, with validator defects separated from data defects.
- Exact producer SHA, run ID, timestamps and source lineage across GitHub, BigQuery and both Google Sheet workbook IDs.
- Actual hosted Colab notebook execution and independently read back outputs, not local notebook validation.
- Real Power BI report/workspace/dataset and successful refresh/readback, or explicitly `NOT_CONFIGURED`.
- Sustained 24/7 watchdog and controlled failure recovery proof.
- GCS WORM gate remains blocked by closed billing; GitHub artifact readback is an alternate proof, not equivalent to GCS WORM.

## Minimal AGY task prompt template

`Read docs/PAPER_PROOF_CLOSURE_RUNBOOK_20261011.md and docs/AGY_PENDING_PROOF_HANDOFF.md. In this isolated worktree, select the highest-priority single unproven gate. First discover inputs and reproduce failure. Make only the smallest safe fix with negative tests. Never change main, trade live, invent market prices, suppress failures, or use paid services. Return structured handoff including every still-unproven gate and your prioritized recommendations. Do not commit/push; independent verifier will review.`

**Scheduling:** This loop is invoked during an active supervised run or an explicitly configured scheduled task. The document itself does not create an unattended process or promise 24/7 execution.

## Mandatory external-evidence discovery and downstream closure (each run)

Before asking the user for any missing external evidence, search the **actual accessible sources** in this order: (a) existing local `data/`, `paper_log.py`, `scripts/forward_validation.py`, `tools/forensic_paper_sheet_audit.py`, `tools/powerbi_inspector.py`, `tools/sync_colab_notebook.py` and `notebooks/ANGEL_FNO_COLAB_RUNNER.ipynb`; (b) authorized GitHub repository/Actions artifacts and workflow logs; (c) authenticated, read-only Google Sheets/BigQuery and Google Drive/Colab artifacts where accessible; (d) authorized Power BI workspace/report metadata where accessible; (e) independent NSE/broker market-data feeds with contractual entitlement and timestamped provenance. Do not claim external access without an actual successful call and readback.

For **every** external input, report `source_name`, `source_type`, `uri_or_local_path` (never a secret URL/token), `permission_status`, `retrieved_at_utc`, `event_time_ist`, `source_run_id`, `sha256`, `schema`, `row_count`, `missing_fields`, `freshness`, `independent_confirmation`, `confidence_limitations`. If unavailable, report exact attempted discovery, error category and the minimum user action; never fabricate a source. Preserve raw source separately from transformations and attach a manifest.

Market prediction acceptance requires immutable forecast timestamp **before** NSE target session, exact symbol+expiry+strike+CE/PE contract key, target session calendar, forecast probability/gap value, independent actual opening bid/ask/last trade with exchange timestamps, quote depth/spread and a realistic executable-paper simulation including fees and slippage. Never treat an underlying open as an option premium open, a quote as a fill, an alert as a trade, or a future market session as completed. Calculate accuracy only for joined verified rows; show numerator/denominator, exclusions, error metrics and confidence intervals. No lookahead or synthetic results.

After receiving an AGY report, independently run downstream validation: parse handoff schema; verify paths exist and hashes match; rerun focused tests; inspect negative cases; compare actual upstream producer against downstream Google Sheets, BigQuery, GitHub and dashboard; rerun live readback when permitted; file a scoped PR and wait for all CI checks before merge; update proof ledger and mark every remaining gap `PENDING`, `BLOCKED`, `FAILED`, or `PASS` with timestamp. Do not stop at agent recommendations or count a report as deployment.

**Prioritized recurring AGY question:** 'Which currently unproven gate can be closed with the inputs already available, what precise raw evidence proves the issue, what smallest tested repair would close it, and which upstream/downstream consumers must be independently rechecked? Include every remaining unproven gate, missing external input, actionable recommendation and next step.' Ask this on each supervised batch; a runbook alone does not schedule execution.

**Manual inputs only if discovery fails:** (1) user-authorized Power BI tenant/workspace/report/dataset or approval to create a new report; (2) authorized hosted Colab notebook/session and output location; (3) legally accessible historical/live NSE option-contract quote/market data with timestamps, if not already available through existing credentials; (4) real PAPER fills/quote-ledger location if generated outside this repository; (5) explicit permission before any new credential connection or paid cloud use. Never request passwords, API keys, or secrets in chat.
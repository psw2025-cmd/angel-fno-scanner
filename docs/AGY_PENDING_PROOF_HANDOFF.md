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

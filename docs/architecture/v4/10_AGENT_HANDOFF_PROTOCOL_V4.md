# AGENT EXECUTION CONTRACT V4 — READ BEFORE ANY WRITE

## One-time start instruction
Read `README_START_HERE.md` and all documents in its reading order. **Inventory before modifying.** Produce `P0_REALITY_SNAPSHOT` in a feature branch, with sources, timestamps, complete branch/PR/workflow DAG, permission readback, resource IDs and honest UNKNOWN values. Run the `validate_package.py` verifier included in this archive. The docs are proposed contracts, not evidence of a deployed platform.

## Tasks in dependency order

1. P0: Read GitHub main and remote refs; PR #98 and #108, all open PR dependencies; existing workflows, provenance schemas, data writers, Cloud Run/Scheduler in all relevant projects/regions, WIF accounts, BQ tables, sheet tabs, Power BI sources, cost controls, Gmail labels and watch capability. Redact secrets. Post `docs/architecture/CURRENT_BASELINE.md` and `ops/state/resource_inventory.json`.
2. P1: Add versioned schemas and evidence index, fail-closed validator, CI negative tests; publish PR. No runtime edit. Show failing fixture => FAIL, passing fixture => TEST_ONLY.
3. P2: Implement cloud read-only auditor + independent readbacks + IAM/WIF; deploy only with actual provisioned authority. Publish clean `capabilities.json` and access-denied cases. Avoid globally privileged service accounts.
4. P3: Fix F&O runtime/lineage only after proving baseline and exact main/feature drift; keep existing entry points. Verify actual PAPER cycle through authenticated Cloud Run execution and sink receipts, not simulated.
5. P4: Cloud orchestration, monitoring and Gmail/PubSub routing; prove alert idempotency, no email-triggered code execution, bounded retries and owner-readable incidents.
6. P5: Ingest survivorship-free point-in-time equity history; prove dates and corporate actions. No model promotion.
7. P6: Construct labels, baselines, market-regime cohorts and 10-year walk-forward; demonstrate out-of-sample parity and no data leaks.
8. P7: Publish immutable prospective equity PAPER forecasts and later independently matured outcomes. Measure benchmark-relative return, risk and real-world entry/exit feasibility.
9. P8: Run independent end-to-end laptop-off, shutdown, stale-source, schema, credential, concurrency, outage, rollback and negative-control drills.
10. P9: Publish a per-domain certification report; only domains with actual independent evidence PASS. Leave others BLOCKED/UNKNOWN with issue and next action.

## Required persistent GitHub board
- `docs/architecture/IMPLEMENTATION_LEDGER.md`: Requirement ID, designated owner, branch, PR, exact SHA, tests, deployment digest, CI, cloud evidence, sink readback, status, blocker, next step.
- `ops/state/current_status.json`: latest machine-readable state; status cannot be self-asserted green from local tests.
- `ops/evidence/index.json`: link each claim to authentic immutable artifact, full digest, time and verifier.
- `docs/architecture/FAILURE_REGISTER.md`: incident root cause, failed invariant, patch, negative control, observed recovery, regression owner.
- GitHub Issue #3: compact summary and links to canonical files; do not overload issue with secrets or full logs.

## Report schema after *each* PR or deployment
- Requirement IDs and impact; `BEFORE` + `AFTER` with independent receipts; exact PR head SHA, target main SHA and merge-base; branch divergence; test count pass/fail/skip; statuses of critical negatives; service account and IAM readback (names only), market calendar session state; deploy commit and image digest; Cloud Run execution ID and status; broker quote times; BQ and Sheets row-level readbacks; Power BI last refresh; rollback artifact; redacted failure diagnostics; who verified; next action and owner-only permission need.
- A passing job is only CI_PASS. A live workflow trigger is not a verified sink write. A dataset match is not model accuracy. Distinguish development, cloud runtime, data publication, and prospective investment measurement.

## Safe self-healing actions allowed under user authority
- Retry transient read operations with limits; rerun isolated tests; edit feature branch; create PR; publish redacted evidence; open/annotate GitHub issues; redeploy/rollback **PAPER** after protected checks and exact-SHA authorization; update cloud monitoring alarms with validated least privilege.
- Deny automatic force-push, branch deletion, clear/reset of dirty worktrees, secret exposure, live trading, changes to real-money risk controls, unreviewed production writes, budget-raising permissions or bypassing required branch gates.
- A permission block must have an exact resource/action, missing role/capability, safest permission request and autonomous workaround if legitimate. No fabricated evidence or silent weakening of gates.

## Final declarations
`DESIGN_HANDOFF_READY` is a statement about the integrity of this package. `CODE_IMPLEMENTED`, `GCP_DEPLOYED`, `DATA_FRESH`, `PAPER_PREDICTING`, `PREDICTION_ACCURATE` and `CLOUD_INDEPENDENT` require separate, fresh and independently auditable evidence. Never conflate these.
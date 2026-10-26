# ANGEL F&O + EQUITY MULTIBAGGER — CLOUD MASTER ARCHITECTURE V1

**Status:** IMPLEMENTATION SPECIFICATION — NOT A PRODUCTION CERTIFICATE  
**Prepared:** 2026-10-26 (Asia/Kolkata)  
**Repository:** `psw2025-cmd/angel-fno-scanner`  
**Proposed GCP project:** `fno-angel-prod-1790444589`, subject to current inventory, IAM and budget confirmation  
**Owner operating constraints:** laptop-independent; PAPER only; nontechnical owner; verifiable evidence; no invented PASS; preserve existing F&O behavior; autonomous repair within controls.

## A. Non-negotiable acceptance policy

1. **Never represent an agent-generated statement as independent proof.** A green build certifies only its actual scope and exact SHA. Evidence produced by a job and its independent readback must be distinguishable.
2. `PAPER_MODE=1`, `LIVE_ORDER_AUTHORITY=0`, `ALLOW_REAL_ORDERS=0` when supported. Absent or contradictory flags block execution. Production service account must have **no broker trading-order capability**. Never use simulated tests as evidence of a live broker or cloud run.
3. F&O canonical universe remains exactly 219 eligible identities under its own contract. Effective-dated ticker rename `ICICIPRULI` → `ICICILIFE` from 2026-10-23 must follow verified broker/exchange instrument identity; historical records retain historical symbols.
4. Options and equity research must have separate writers, leases, datasets/tables, buckets/prefixes, model registries, job identities and alert streams. Share libraries, read-only source snapshots and the audit control plane only.
5. No force-push, reset, broad clean, unreviewed deletion, automatic promotion of failed tests, secret disclosure, no unreviewed trading deployment. Do not merge PR #98 or PR #108 merely because tests elsewhere passed.
6. Long-horizon equity must remain `SCAFFOLD/PAPER/BLOCKED` until survivorship-free ingestion, point-in-time replay, prospective forecasts, benchmark comparison and matured-outcome evidence pass. No claim of successful multibagger predictions or 10× returns until proven.
7. **Fail closed** for missing upstream inputs, stale evidence, unknown exact SHA, branch drift, missing permissions, mismatched timestamps, data leaks, duplicate symbols, nonfinal exchange data and missing downstream readbacks. `NOT_RUN`, `UNKNOWN`, `BLOCKED` are not PASS.
8. Do not treat `gcloud run jobs execute ... --wait` returning exit zero as proof of actual 219 valid market rows. It proves the process completed; mandatory readback follows.
9. Every cloud asset, API, secret and permission is inventory-checked before create; use declarative desired state; no duplicate resources or cost surprises.
10. Every task must declare whether it is `IMPLEMENTED`, `DEPLOYED`, `VERIFIED`, or `CERTIFIED`; those stages are not synonymous. Generate a traceable evidence ID for each claim.

## B. Current state versus proposed state (as known 2026-10-26)

| Area | Grounded current position | Target | Evidence still required |
|---|---|---|---|
| Primary repo `main` | Existing F&O code/workflows; Phase 5 not in `main` | Protected consolidated monorepo | branch protection readback + protected PR |
| CDX PR #98 | Open draft on feature branch (as checked) | Independently reviewed safe integration | exact head SHA, full CI, migration impact |
| Phase 5 PR #108 | Open draft; scaffold files, fail-closed EOD | Additive equity ingestion in main | validation and activation contract |
| Historical Phase 5 | `src/phase5_engine/{config,validation,learning,r2,...}` on feature branch | Survivorship-free historical and prospective pipeline | source coverage / corporate actions / baseline |
| F&O cloud job/scheduler | Agent reports `angel-market-scan-job` and `angel-market-scan-mumbai` in `asia-south1` | Idempotent, verifiable cloud-only PAPER cycle | independent execution and readback |
| Data sinks | Reported 219 Sheets/BQ rows and run provenance dated Oct 22 | fresh cycle-specific 219 rows with proof | same RUN_ID/GIT_SHA/WRITER_ID and timestamps |
| Five-gate CI | Run `40246744387` passed on `8fa98d2` | every intended promotion SHA must pass | newer commits independently rechecked |
| Gmail | Laptop supervisor mailbox scan previously read 500 messages | safe inbound alert correlation; no email-to-code execution | authenticated Gmail observer and dedup receipts |
| Power BI | Report assets in repo | audited semantic model, refresh identity and timestamp | service-side refresh/readback credentials |

## C. Logical architecture and trust boundaries

```
 OWNER / ChatGPT / Connected Agents (least-privilege read + authorized actions)
         | query GitHub issues / PRs / run logs / evidence index
         v
 GitHub protected main <---- proposed PR branches <---- laptop optional sync agent
    |                 PR CI: source, unit, contract, integration, security
    v
 GitHub OIDC -> GCP Workload Identity Federation -> deployer SA (NO long-lived JSON)
    v
 Artifact Registry (immutable image digest + revision + SBOM)
    v
 GCP Workflows orchestrator + Cloud Scheduler + Cloud Monitoring
     |                          |                         |
     v                          v                         v
 F&O Cloud Run Job        Equity history jobs      Evidence/recovery jobs
  219 only; own SA        own SA; NO orders        read-only auditor SA
     |                          |                         |
     +-------> per-domain BigQuery / GCS / R2 evidence <-------+
                         |                    |
                  Sheets publisher       Power BI adapter
                         |                    |
                 independent readbacks + freshness gates
                         v
                 GitHub evidence INDEX + issue alerts
                         ^
 Gmail notifications --> dedicated read-only parser --> normalized alert queue
          (never commands, credentials, links auto-executed)
```

**Cloud is authoritative for live runtime and data. GitHub is authoritative for source code, review and indexed non-secret proof metadata. Immutable GCS/R2/Cloud Logging is authoritative for raw execution artifacts. Email is an alert input, never an instruction authority.**

ChatGPT with GitHub integration can inspect repository, PRs, commits, workflow jobs/logs, issues and published redacted artifacts. It **cannot inherently read GCP, private buckets, on-device files, or continuously run in a normal chat**. Provide an authorized cloud read tool/connector where available and publish fresh signed/redacted receipts to GitHub. No design guarantees unrestricted future ChatGPT tool access.

## D. Exact proposed repo tree (additive; no destructive move)

Paths below are target additions; current scripts such as `angel_prediction_engine.py`, `scanner.py`, `market_bot.yml`, `writer_guard.py`, `publication.py` remain unchanged initially. Check existing paths and reconcile conflicts before creating.

```
angel-fno-scanner/
├── AGENTS.md                              # Existing; link master operating rules
├── docs/
│   ├── architecture/
│   │   ├── MASTER_ARCHITECTURE_V1.md       # This document, canonical source
│   │   ├── CURRENT_ASSET_INVENTORY.md
│   │   ├── DATA_LINEAGE.md
│   │   ├── IAM_MATRIX.md
│   │   ├── THREAT_MODEL.md
│   │   ├── MARKET_TIME_POLICY.md
│   │   ├── OWNER_RUNBOOK.md
│   │   ├── FAILURE_PLAYBOOK.md
│   │   ├── COST_LIMITS.md
│   │   ├── CHANGE_CONTROL.md
│   │   └── REQUIREMENT_TRACEABILITY.csv
│   ├── phase5/
│   │   ├── 10_YEAR_DATA_SOURCE_MANIFEST.md
│   │   ├── SURVIVORSHIP_AND_CORPORATE_ACTION_POLICY.md
│   │   ├── LABELS_2X_3X_5X_10X_20X.md
│   │   ├── LEAKAGE_AND_WALK_FORWARD_PROTOCOL.md
│   │   ├── MODEL_ACCEPTANCE_POLICY.md
│   │   └── MARKET_BENCHMARK_METHOD.md
│   └── CHANGELOG.md
├── config/
│   ├── runtime_contract.yaml
│   ├── evidence_contract.yaml
│   ├── resources_manifest.yaml
│   ├── deployment_policy.yaml
│   ├── gmail_alert_rules.yaml
│   └── phase5/
│       ├── source_registry.yaml
│       ├── universe_policy.yaml
│       ├── corporate_action_policy.yaml
│       ├── feature_registry.yaml
│       ├── label_policy.yaml
│       ├── model_policy.yaml
│       └── market_calendar_policy.yaml
├── src/
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── security_identity.py            # ISIN, effective-dated symbols, broker tokens
│   │   ├── market_clock.py                # IST holidays/session gates
│   │   ├── provenance.py                  # canonical RUN_ID/SHA/writer/source digests
│   │   ├── idempotency.py
│   │   ├── receipts.py                    # content hashes, signature verification
│   │   ├── result_state.py                # PASS/FAIL/BLOCKED/UNKNOWN
│   │   └── audit_logger.py
│   ├── options_adapter/
│   │   ├── __init__.py
│   │   ├── existing_engine_bridge.py      # initially calls existing stable modules
│   │   ├── publication_contract.py
│   │   └── paper_cycle_receipt.py
│   ├── phase5_engine/                     # import or adapt PR #108 scaffold safely
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── validation.py
│   │   ├── learning.py
│   │   ├── r2.py
│   │   ├── schema.json
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── nse_daily.py
│   │   │   ├── bse_daily.py
│   │   │   ├── security_master.py
│   │   │   ├── financial_filings.py
│   │   │   ├── corporate_actions.py
│   │   │   ├── delisted_suspended.py
│   │   │   ├── source_inventory.py
│   │   │   └── quarantine.py
│   │   ├── identity/
│   │   │   ├── historical_instruments.py
│   │   │   ├── isin_events.py
│   │   │   └── symbol_aliases.py
│   │   ├── quality/
│   │   │   ├── continuity.py
│   │   │   ├── prices_adjustment.py
│   │   │   ├── outlier_review.py
│   │   │   ├── point_in_time.py
│   │   │   └── coverage_report.py
│   │   ├── features/
│   │   │   ├── fundamentals.py
│   │   │   ├── price_volume.py
│   │   │   ├── relative_strength.py
│   │   │   ├── sector_regime.py
│   │   │   └── news_event_time.py
│   │   ├── labels/
│   │   │   ├── forward_multiple.py
│   │   │   ├── horizon_maturity.py
│   │   │   └── investability.py
│   │   ├── models/
│   │   │   ├── naive_baselines.py
│   │   │   ├── momentum_baseline.py
│   │   │   ├── gradient_boosting.py
│   │   │   ├── calibrate.py
│   │   │   └── registry.py
│   │   ├── backtest/
│   │   │   ├── chronological_splits.py
│   │   │   ├── execution_simulator.py
│   │   │   ├── benchmarks.py
│   │   │   ├── bias_guard.py
│   │   │   └── report.py
│   │   ├── forecasts/
│   │   │   ├── paper_ranker.py
│   │   │   ├── immutable_publisher.py
│   │   │   └── outcome_matcher.py
│   │   └── portfolio/
│   │       ├── paper_ledger.py
│   │       ├── slippage_liquidity.py
│   │       └── risk_metrics.py
│   └── control_plane/
│       ├── __init__.py
│       ├── inventory.py
│       ├── github_inspector.py
│       ├── cloud_inspector.py
│       ├── bq_sheet_reconciler.py
│       ├── powerbi_inspector.py
│       ├── pipeline_health.py
│       ├── gmail_ingestion.py
│       ├── alert_correlator.py
│       ├── issue_manager.py
│       ├── recovery_decider.py
│       ├── receipt_indexer.py
│       └── certification.py
├── services/
│   ├── options-paper/entrypoint.py
│   ├── equity-history/entrypoint.py
│   ├── equity-features/entrypoint.py
│   ├── equity-backtest/entrypoint.py
│   ├── equity-paper/entrypoint.py
│   ├── equity-outcomes/entrypoint.py
│   ├── evidence-auditor/entrypoint.py
│   └── gmail-event-receiver/entrypoint.py
├── infra/
│   ├── terraform/
│   │   ├── versions.tf
│   │   ├── providers.tf
│   │   ├── variables.tf
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── iam.tf
│   │   ├── oidc.tf
│   │   ├── cloud_run_jobs.tf
│   │   ├── scheduler.tf
│   │   ├── workflows.tf
│   │   ├── pubsub.tf
│   │   ├── artifact_registry.tf
│   │   ├── bigquery.tf
│   │   ├── buckets.tf
│   │   ├── monitoring.tf
│   │   └── environments/{sandbox,paper-prod}.tfvars.example
│   ├── workflows/
│   │   ├── options_daily.yaml
│   │   ├── phase5_eod.yaml
│   │   ├── phase5_validation.yaml
│   │   ├── phase5_weekly_learning.yaml
│   │   └── failure_recovery.yaml
│   └── docker/
│       ├── options.Dockerfile
│       ├── equity.Dockerfile
│       └── auditor.Dockerfile
├── .github/
│   ├── CODEOWNERS
│   ├── ISSUE_TEMPLATE/{runtime_incident,ci_failure,data_lineage_gap}.yml
│   ├── pull_request_template.md
│   └── workflows/
│       ├── market_bot.yml                    # existing, retain contract
│       ├── nightly_verify.yml                # existing; correct independently
│       ├── pr_tests.yml                      # existing; harden exact-SHA tests
│       ├── phase5_eod.yml                    # existing scaffold PR #108; later activate
│       ├── phase5_validation.yml
│       ├── phase5_learning.yml
│       ├── cloud_paper_deploy.yml
│       ├── cloud_evidence_audit.yml
│       ├── historic_backfill_manual.yml
│       ├── config_drift_watch.yml
│       ├── data_contract_tests.yml
│       └── owner_health_summary.yml
├── ops/
│   ├── scripts/
│   │   ├── inventory_gcp.py
│   │   ├── inspect_github.py
│   │   ├── check_iam_least_privilege.py
│   │   ├── check_scheduler.py
│   │   ├── reconcile_current_cycle.py
│   │   ├── export_redacted_receipts.py
│   │   ├── verify_cloud_safety.py
│   │   ├── check_powerbi_refresh.py
│   │   └── assemble_owner_certification.py
│   ├── laptop_sync/
│   │   ├── SafeSync.ps1
│   │   ├── InstallTask.ps1
│   │   ├── ExportBackup.ps1
│   │   └── README.md
│   └── runbooks/
│       ├── options_feed_failure.md
│       ├── cloud_job_failed.md
│       ├── duplicate_writer.md
│       ├── bq_sheet_mismatch.md
│       ├── missed_eod.md
│       ├── gmail_alert_burst.md
│       └── rollback.md
├── schemas/
│   ├── execution_receipt.schema.json
│   ├── prediction_receipt.schema.json
│   ├── outcome_receipt.schema.json
│   ├── audit_claim.schema.json
│   ├── dependency_inventory.schema.json
│   ├── failure_event.schema.json
│   ├── data_source_manifest.schema.json
│   └── paper_portfolio.schema.json
├── sql/
│   ├── control/{asset_inventory,execution_ledger,alerts,incidents,verification_claims}.sql
│   ├── options/{options_readback,paper_cycle_provenance}.sql
│   └── equity/{security_master_history,prices_eod,corporate_actions,filings_pit,universe_daily,features_pit,predictions_paper,outcomes,models,portfolio_ledger}.sql
├── tests/
│   ├── shared/
│   ├── options_integration/
│   ├── phase5/
│   │   ├── test_survivorship.py
│   │   ├── test_symbol_rename.py
│   │   ├── test_corporate_actions.py
│   │   ├── test_point_in_time.py
│   │   ├── test_future_leakage.py
│   │   ├── test_2x_10x_labels.py
│   │   ├── test_illiquid_uninvestable.py
│   │   ├── test_walkforward.py
│   │   ├── test_immutable_forecasts.py
│   │   └── test_paper_only.py
│   ├── control_plane/
│   │   ├── test_missing_run_blocks.py
│   │   ├── test_mismatched_shas_block.py
│   │   ├── test_stale_bq_sheet_blocks.py
│   │   ├── test_missing_gmail_permission_blocks.py
│   │   ├── test_email_injection_ignored.py
│   │   ├── test_cloud_retry_idempotence.py
│   │   └── test_false_green_negative_controls.py
│   └── end_to_end/
│       ├── test_options_paper_receipt.py
│       └── test_equity_paper_receipt.py
└── evidence/README.md                       # INDEX ONLY, no logs/secrets/raw PII
```

**Migration rule:** `options_adapter` is only an adapter, not an immediate rewrite. Repo layout is a proposal; staged changes are split into small PRs with explicit compatibility tests.

## E. GCP resources and service accounts (proposed names)

**Inventory first** the project id, region, Cloud Run job, scheduler, secrets, IAM, services, billing alert budgets, existing writer lease. Example names below are desired-state proposals, not declarations that assets exist.

| Proposed resource | Name / role | Restrictions |
|---|---|---|
| Cloud Run F&O | existing `angel-market-scan-job` in `asia-south1` | PAPER only, existing writer, 219 contract |
| Scheduler F&O | existing/reported `angel-market-scan-mumbai` | calendar/holiday gate inside app; do not duplicate |
| Cloud Run history | `equity-history-ingest-job` | read external data, write raw+staging only |
| Cloud Run point-in-time | `equity-feature-build-job` | write feature tables; no trading |
| Cloud Run backtest | `equity-walkforward-job` | controlled compute, no deployed promotion |
| Cloud Run equity predict | `equity-paper-forecast-job` | model read, append-only forecasts, no broker orders |
| Cloud Run outcomes | `equity-outcome-verify-job` | post-maturity evaluation |
| Cloud Run audit | `system-evidence-auditor-job` | read-only BQ and Sheets, write evidence to isolated store |
| Cloud Run Gmail | `gmail-alert-receiver` (only if direct Gmail connection authorized) | safe inbound Pub/Sub auth, no command execution |
| Orchestration | `angel-options-workflow`, `equity-eod-workflow`, `equity-weekly-workflow` | dependency and retry policy |
| Pub/Sub | `system-health-events`, `gmail-alert-events` | dead-letter policy, dedup |
| GCS | `gs://<unique>-angel-evidence` | object retention/versioning, IAM segmentation |
| Artifact Registry | `asia-south1-docker.pkg.dev/<project>/angel-paper/...` | digest-pin deployment |
| BigQuery existing | `fno_predictions` | preserve options writer and tables |
| BigQuery equity | `equity_research_raw`, `equity_research_pit`, `equity_research_results` | append/staging partition; per-role IAM |
| BigQuery audit | `system_control` | append-only execution/claims |
| Secrets | Secret Manager references only | service account scoped; no secrets in repo or issues |
| Monitoring | alert policies + dashboards | per-engine heartbeat, log error, quotas, freshness |

**Service identities:** `gha-paper-deployer`, `options-paper-runner`, `equity-history-reader`, `equity-features-writer`, `equity-paper-publisher`, `evidence-readback-auditor`, `gmail-alert-parser` (subject to IAM service-account name limits and current resource reconciliation). Deployers may update only allowlisted PAPER jobs; runners cannot change IAM, branch protection or source code. Prefer WIF/OIDC and restrict GitHub OIDC claims to repo, protected refs and approved environment. Scheduler invoker gets only `run.jobs.run` or the specific invocation permission needed, not broad editor.

**Billing:** dry-run estimates; budgets and alerts at owner-approved thresholds; BigQuery per-query bytes caps; cloud job maximum runtime, concurrency and retries; data-retention and storage lifecycle by evidence class. Failure to inspect budget is a deployment blocker, not a reason to assume free tier.

## F. Schedules, calendar and reliability

- India market day and holiday calendar: authoritative calendar snapshot with source URL, retrieval timestamp and SHA; do not use weekdays alone.
- Existing options: preserve broker/exchange validity windows and 09:15–15:30 session with relevant 15:40 guard and source freshness.
- Equity EOD: **earliest desired** 16:00 IST on eligible trading days, execute only after confirmed EOD source arrival and integrity checks; no fixed-time assumption.
- Next-session gap verification: 09:16 IST after exchange open data validated; this is separate from 3–12-month equity outcome maturation.
- Long-horizon outcomes: daily check all forecasts whose target horizons have matured, using total-return-adjusted prices and benchmark alignment.
- Weekly research: weekend on completed data only; challenger cannot self-promote without evidence.
- Heartbeat: hourly cloud monitor plus event-triggered incident alerts. A 24/7 cloud operator should not require a laptop Windows session.
- Retry: bounded exponential backoff with jitter on transient faults; DLQ after max attempts; dedup idempotency key `engine|market_date|run_id|model_sha`.
- Distinguish `CLOSED_MARKET`, `SOURCE_NOT_YET_PUBLISHED`, `STALE`, `BLOCKED_CREDENTIAL`, `FAILED`, `PASS` rather than marking every inactive market period FAIL.

## G. Canonical contracts and database logic

**Run identity:** `execution_id` (UUID), `engine` (`options`/`equity`), `run_id`, `git_sha` (full 40), `image_digest` (`sha256:...`), `writer_id`, `market_date_ist`, `data_as_of_utc`, `source_snapshot_id`, `model_id`, `start_utc`, `finish_utc`, `config_digest`, `source_manifest_digest`, `result`, `evidence_object_uri`, `receipt_digest`, `signer_key_id` (if signed). Use immutable append-only record and cross-sink exact tuple.

**Equity security identity:** persistent internal security ID, ISIN, exchange, symbol valid_from/valid_to, listing/delisting events, adjustment factor history; never use a bare ticker as durable entity key. Include delisted, suspended, illiquid, mergers, demergers, changes of company identity, data gaps and stale quote controls. Distinguish exchange timestamp, publication timestamp, ingestion timestamp and model prediction timestamp.

**Price returns:** both adjusted close-to-close endpoint and intrahorizon threshold-crossing; explicit dividends, bonus, splits, rights, spin-offs; return after realistic spread, slippage, turnover cap, lot/volume constraints and exit feasibility. Distinguish market-cap multiplier from actual shareholder return.

**Lookahead prevention:** every feature has `known_at_utc`; features must satisfy `known_at_utc <= prediction_issued_at_utc`. Filings use actual announcement availability, not financial period end. Purge overlapping label horizons and embargo windows when selecting folds. Include stocks before exclusion/delisting. Archive source versions and revisions.

**Prediction evidence minimum:** `prediction_id`, `security_id`, historical exchange ticker, issue timestamp (UTC+IST), horizon, probability for each 2x/3x/5x/10x/20x threshold (if calibrated), forecast return distribution, entry reference price, available liquidity, data watermark, model SHA, feature snapshot hash, code SHA, run ID, signed immutable object ID, `paper_only=true`, and explicit `NOT_YET_EVALUATED` status.

**Outcome evidence:** `prediction_id`, horizon maturity rule, market observations and vendor IDs, available execution assumptions, benchmark TRI over same dates, observed threshold crossing (if any), end-period return, realized-paper ledger return, data gaps, confidence calibration, review status, evidence hash. Never mark future forecasts correct early.

**Suggested SQL semantics:** create raw immutable ingestion (`source_uri`, `source_sha256`, `ingested_at`, `effective_date`), bitemporal event tables (`valid_from`, `valid_to`, `known_at`), append-only predictions keyed by `prediction_id`, validation keyed by `prediction_id|horizon|method_version`, model registry keyed by artifact digest, and `system_control.execution_ledger` keyed by execution ID. Enforce duplicates in application checks and reconciliation (BigQuery uniqueness is not a substitute for validation).

## H. Independent evidence package — mandatory outputs

**Do not push private raw broker credentials, Gmail message bodies, user identities, signed URLs or secret values to GitHub.** GitHub should contain only non-sensitive pointers/hashes/statuses with authenticated cloud backing. For every execution produce immutable artifacts at stable versioned key pattern:

`gs://<evidence-bucket>/<engine>/<YYYY-MM-DD>/<execution_id>/...` (cloud)

And a small redacted digest-only GitHub summary under `docs/ops_evidence/YYYY/MM/DD/<engine>_<runid>_summary.json` via controlled artifact publishing PR, **or** GitHub Actions artifacts attached to the immutable GitHub workflow run. Avoid recursive GitHub commit loops. Issue #3 can act as human-readable shared board if maintained, not as sole immutable evidence.

Required bundle:

```
00_manifest.json
01_asset_inventory.json
02_source_data_coverage.json
03_schedule_and_executions.json
04_ci_exact_sha.json
05_security_safety.json
06_options_cycle_provenance.json
07_bigquery_sheets_reconciliation.json
08_powerbi_source_refresh.json
09_equity_pit_data_integrity.json
10_equity_model_backtest.json
11_forward_predictions.json
12_matured_prediction_outcomes.json
13_paper_portfolio_metrics.json
14_gmail_alert_digest.json
15_incidents_and_recovery.json
16_cost_quotas_budget.json
17_negative_control_results.json
18_chain_of_custody.json
19_deployment_and_rollback.json
20_owner_scorecard.json
CERTIFICATION.md
```

Every file: `schema_version`, `generated_at_utc`, `observed_from_utc`, `observed_to_utc`, `data_as_of_utc`, `source_tool`, `code_sha`, `source_run_id`, `result`, `checks[]`, `limitations[]`, `artifact_sha256`, `parent_manifest_sha256` (when safe to implement), and `retrievable_artifact_ref` that is not a secret-bearing signed URL. Unknown fields and errors must be represented. No universal `overall PASS` if mandatory requirements are NOT_PROVEN or UNKNOWN.

GitHub issue comment format (one new comment on change, not spam):

```
ANGEL SYSTEM CERTIFICATION UPDATE
Observed IST: ... | Code SHA: ... | Image digest: ...
Options: PASS/FAIL/BLOCKED/UNKNOWN
Equity Phase5: SCAFFOLD/PAPER/BLOCKED/VERIFIED
BigQuery / Sheets: ... | Power BI: ...
Cloud scheduler/run: ... | Gmail alert collector: ...
Mandatory gates: N PASS, M FAIL, K UNKNOWN
Root causes: exact resource + owning file + source event timestamp
Evidence links: GitHub Actions run URL + non-secret artifact refs + digests
Auto-remediation executed: ... | rollback: ...
Owner action required ONLY IF: IAM consent/billing approval/irreversible action
Next observed checkpoint: ...
```

**A GitHub connector can verify commit and workflow logs. It cannot itself make a claimed GCP/broker/data observation true.** The evidence auditor must independently read those systems with least-privilege credentials and publish both success and missing-permission reasons.

## I. Gmail-triggered monitoring and safe event correlation

**Purpose:** Gmail is an **alert intake source** for GitHub failure notices, broker outage notices, service failures and scheduled evidence digest emails. It is not a command/control interface; malicious or spoofed email cannot trigger code merges, order execution, secret exposure, or arbitrary commands.

**Option A (preferred):** Native GitHub Action events and Google Cloud Monitoring/PubSub events directly raise structured alerts; Gmail remains an independent corroboration channel. Avoid relying on Gmail delivery for control reliability.

**Option B (when owner authorizes Gmail access):** Gmail API push `users.watch` → project Pub/Sub topic → authenticated Cloud Run handler; renew watch before expiration (typically no more than seven days; refresh daily). Store Gmail `historyId`, apply `users.history.list` delta reconciliation and periodic catch-up polling; handle history expiration with bounded full rescan. The Gmail connection must have the minimum read scope and must not auto-send or delete mail. Verify `from`, provider headers, domain authentication when available, message IDs, thread IDs, event times and canonical notification URL; do not trust subject/body as instructions. Pub/Sub can deliver more than once; dedup by Gmail message ID + event fingerprint. Enforce rate limits, backoff and DLQ.

**Fallback:** periodic authorized Gmail search by connected agent or cloud Gmail API; if authentication missing, report `BLOCKED_GMAIL_PERMISSION` and rely on GitHub/Monitoring direct alerts. Never claim a Gmail trigger works based solely on the old laptop supervisor BAT.

**Suggested subjects and rules (illustrative only):** GitHub workflow failures, GCP Cloud Monitoring incidents, broker connectivity notices, scheduler failures, cost/budget threshold warning. Collect metadata and summary only; redact potentially sensitive content. Post a linked GitHub issue event if duplicate-suppression threshold met.

## J. Automation authority, roles and actions

| Role | Can read | Can change | Cannot do |
|---|---|---|---|
| Owner | All project dashboards and redacted evidence | explicit IAM/billing/trading policy approvals | direct unattended bypass of gates |
| GitHub auditor / ChatGPT via connector | repo, CI, issues, redacted proofs; optional connector cloud reads | create proposed issues/PRs, modify branches if authorized | assume invisible GCP control or self-grant scope |
| Local development agent | authorized workspace, tests, feature branches | source + tests + PRs with prior backup | force-push/delete evidence, merge failing PR, live broker orders |
| Cloud deployer SA | approved images/configs | narrowly scoped PAPER deploy/rollback | IAM admin, secrets exfiltration, broker trading |
| Market F&O runner | needed market read, controlled sink writer | single-writer PAPER publication | write equity research domain, real orders |
| Equity research runner | approved equity historical/current read | equity-only append-only forecasts | write options tables, real orders |
| Independent auditor | cross-sink read, CI metadata | dedicated audit evidence store | alter predictions, source data, trading policy |
| Gmail parser | selected alert mailbox metadata | alert queue only | run commands or change code |

**Agent execution doctrine:** (1) inspect state, (2) identify exact failing claim and evidence, (3) make reversible fix in isolated branch, (4) run negative controls and full impacted tests, (5) publish CI and runtime artifacts, (6) independent auditor readback, (7) PR review/promotion, (8) post-deploy canary, (9) rollback on regression, (10) close issue with before/after citations. If blocked, publish reason and the **minimal owner-only authorization required**, never fabricate success.

## K. CI, CD, and release policy

- On PR: scope/path change detection; `git diff` contract and docs; dependency/license/SBOM/supply-chain scan; Python lint/type/encoding, core and full suite; negative controls; independent F&O/Phase 5 tests; branch protection exact head SHA; optional cloud read-only contract; no production credentials exposed to fork/untrusted code. Default read-only `GITHUB_TOKEN` where possible. Separate privileged validation using trusted code pinned to protected SHA after review.
- Require main protection and approvers. `branch-protection-gate` cannot be declared required until actual observed status context exact name, check origin and protected-branch rules verified. At least one independent approval for production deployment/security-policy changes.
- Promotion: CI artifact digest + git SHA → immutable container image → deploy sandbox/PAPER staging → canary → independent readback → protected paper-prod deployment. Never deploy mutable `latest` tags or branch tip implicitly.
- On `main` push: build pinned digest and verify WIF subjects, service-account scope; no push-to-live-order automation. Do not grant `contents: write` / `issues: write` to all jobs unless justified.
- On test failure: block. On missing external Colab contract: BLOCKED, do not generate a replacement fixture or skip mandatory assurance while calling it pass.
- Cloud runtime: verify execution ID, Cloud Run execution terminal status and exit, logs, data watermark, engine identity, model revision, sink record run ID, exact image digest, and no duplicate lease writer.
- Rollback: last certified image digest + corresponding schema/contract; never rollback data by overwriting immutable forecasts; append correction events. Freeze promotion on corruption.

## L. Stepwise implementation plan with end-to-end acceptance

### P0: Baseline, inventory, preservation
**Files:** `docs/architecture/CURRENT_ASSET_INVENTORY.md`, `config/resources_manifest.yaml`, `ops/scripts/inventory_gcp.py`.  
**Actions:** GitHub main/head, PR#98/#108, branch drift, CI run history, cloud jobs/schedulers, IAM, Cloud Run images, BQ schemas and counts, Sheets/PBI, Gmail availability, GCP billing and existing evidence bucket; retain snapshots and hashes.  
**Exit:** all current assets and owners categorized `VERIFIED/NOT_FOUND/NO_ACCESS`, immutable backup; no duplicate job created.

### P1: Observability and evidence contracts **FIRST**
**Files:** `schemas/*.schema.json`, `src/control_plane/*`, `src/shared/receipts.py`, `docs/architecture/DATA_LINEAGE.md`, `cloud_evidence_audit.yml`.  
**Actions:** implement no-secret evidence publication and reconciliation, negative test false-greens, GitHub evidence index, incident issue template.  
**Exit:** deliberately broken run IDs, missing source, stale 219, wrong SHA, duplicate writer, missing Gmail/PBI must all **fail**; independent readback succeeds on a known valid mock/staging cycle. No certification from generated self-claims.

### P2: Cloud identity + deployment foundation
**Files:** `infra/terraform/{iam,oidc,...}.tf`, `config/deployment_policy.yaml`, `cloud_paper_deploy.yml`.  
**Actions:** owner-approved least-privilege WIF; secrets inventory and migration (no export of values); billing guardrails; protected CI; signed/digested image; cloud job deployment and rollback.
**Exit:** authenticated read-only cloud inspection and controlled sandbox deployment; no broad cloud owner roles; rollback canary observed.

### P3: Preserve and certify F&O PAPER engine
**Files:** `src/options_adapter/*`, `ops/scripts/reconcile_current_cycle.py`, `tests/options_integration/*`.  
**Actions:** reuse 219 universe and existing market_bot writer, correct effective-dated ticker identity, single writer lease, freshness gates, cloud execution and BigQuery/Sheets parity; validate Power BI if access exists.
**Exit:** completed normal market-day PAPER cycle: exact 219 with approved identity, `RUN_ID/GIT_SHA/WRITER_ID/image_digest`, readbacks, market-time correctness and no live order capability. Historical Oct22 rows are *not* current runtime proof.

### P4: Equity 10-year ingestion (Phase 5 foundational scope)
**Files:** `src/phase5_engine/ingestion/*`, `/identity/*`, `/quality/*`, `config/phase5/source_registry.yaml`, `sql/equity/*`, `historic_backfill_manual.yml`.
**Actions:** licensed NSE/BSE historical EOD/financial filings and company master, historical constituents including delisted, symbol corporate-action ledger, PIT timestamps, immutable raw snapshots, anomaly quarantine, source coverage by year/exchange, request-limited backfill.
**Exit:** audited 2016–2026 market-year coverage with explicit known gaps; survivorship bias adversarial tests and corporate-action replay pass. No model live claims.

### P5: Forensic 2×/3×/5×/10×/20× research and baseline backtests
**Files:** `src/phase5_engine/{features,labels,models,backtest}/*`, `docs/phase5/{LABELS...,LEAKAGE...,MARKET_BENCHMARK_METHOD}.md`.
**Actions:** investability filters, true adjusted returns, matured labels 3/6/12-month and optional 24/36-month separately, historical event fundamentals and news, baselines first, rolling PIT walk-forward folds, Nifty 500 TRI and comparable segments, fees, slippage, max drawdown, precision@k, recall, calibration, confidence intervals and sector/regime splits.
**Exit:** nonleaky 10-year replay, compare versus simple momentum/quality baseline. Fail if insufficient sample or robust advantage absent; charts never advertise investment returns as guaranteed.

### P6: Forward-only equity PAPER predictions
**Files:** `src/phase5_engine/forecasts/*`, `services/equity-paper/entrypoint.py`, `phase5_eod.yml`, immutable R2/GCS evidence.  
**Actions:** only pre-outcome issue; freeze forecasts, independent timestamp, cross-source data watermark, explicit target date and horizon, ranked candidate evidence.  
**Exit:** future issued receipts independently retrievable and not overwriteable. Model cannot be judged successful until outcomes mature.

### P7: Equity outcome matching and PAPER ledger
**Files:** `src/phase5_engine/portfolio/*`, `services/equity-outcomes/entrypoint.py`, `phase5_validation.yml`, `sql/equity/outcomes.sql`.  
**Actions:** validate T+1 gap separately from 3–12-month returns, mark PENDING until appropriate maturity, actuals source identity, benchmark matching, portfolio slippage and drawdowns.  
**Exit:** reconciled results for prospectively matured cohort, missing/adjusted data flagged, no prior prediction edits.

### P8: Model learning and challenger governance
**Files:** `src/phase5_engine/learning.py`, `model_policy.yaml`, `phase5_learning.yml`, model registry.  
**Actions:** challenger vs incumbent, minimum >=100 eligible independent observations, uncertainty, multiple-testing controls, anti-leakage, drift, rollback, model review.  
**Exit:** only versioned code and model artifacts with proof; automated research model promotion may be allowed *within PAPER* only under owner-approved risk policy, never real orders.

### P9: Gmail alert correlation and issue triage
**Files:** `src/control_plane/gmail_ingestion.py`, `gmail_alert_rules.yaml`, Pub/Sub receiver, incident templates.  
**Actions:** owner-authorized read scope, Gmail watch/history or polling, authorized senders, dedup and cross-correlate GitHub/Cloud logs, safe issue publication.  
**Exit:** test real alert delivery, duplicate detection, spoofed email ignored, Gmail outage alerts explicitly, no email-to-command path.

### P10: Unified owner dashboard and Power BI
**Files:** `frontend/` changes under PR; new read-only endpoints and metrics; `ops/scripts/check_powerbi_refresh.py`.  
**Actions:** options PAPER + equity PAPER + predictions-vs-outcomes + readiness + current SHA + evidence download and per-source freshness; distinguish market closed, not run, skipped and blocked.  
**Exit:** dashboard values exactly match BQ readbacks and artifact provenance; PBI refresh independently verified rather than inferred from Sheet/BQ.

### P11: Autonomy / recovery exercise
**Files:** `src/control_plane/recovery_decider.py`, recovery runbooks, chaos and negative tests.  
**Actions:** unplug laptop, run market/cloud schedules; deliberately disconnect mock broker, revoke read permission in staging, simulate Pub/Sub duplicate, BQ quota, stale source, 218/220 records, GitHub outage; verify bounded retries and incident filing.  
**Exit:** cloud remains autonomous while laptop off; no false-green, duplicate writer or irreversible action; publish outage/recovery receipts.

### P12: Final acceptance / certification
**Files:** `CERTIFICATION.md`, complete evidence pack, owner dashboard status, release manifest.  
**Actions:** independent auditor recomputes hashes, source-to-sink lineage, tool permissions, current cloud revision and exact commit across all mandatory gates; split certifications `FNO_PAPER_OPERATIONS`, `EQUITY_HISTORICAL_DATA`, `EQUITY_FORWARD_PAPER`, `EQUITY_PREDICTION_PERFORMANCE`.  
**Exit:** all mandatory areas PASS for corresponding scope, no hidden UNKNOWN/NOT_PROVEN. If any fail, scoped certification BLOCKED; other scopes may remain certified.

## M. Acceptance-test matrix (at least these negative controls)

| Injected condition | Expected automated result |
|---|---|
| 218 or 220 instead of 219 F&O identities | BLOCKED before sinks |
| duplicate broker token/ISIN conflicting corporate action | BLOCKED + issue |
| unchanged `run_id` reused across market cycles | FAIL + no publication |
| BQ updated but Sheets stale | FAIL cross-sink gate |
| Sheets and BQ count 219 but symbols differ | FAIL checksum/exact-set |
| same counts and symbols but differing writer/SHA/UTC event | FAIL provenance |
| prediction published after actual price available | invalid label and no backtest credit |
| delisted stock missing from historical universe | FAIL coverage |
| adjusted return fabricated by split/rights mistake | quarantine |
| portfolio return ignores volume and execution limits | FAIL investability |
| insufficient 12-month matured forecasts | `NOT_YET_EVALUABLE` |
| GitHub workflow passed earlier SHA only | `UNKNOWN_EXACT_SHA_CI` |
| cloud job exit 0 but no valid prediction rows | FAIL publication |
| cloud job scheduled but missed market-cycle completion | FAIL or source_not_ready with bounded retry |
| Gmail watch expired or unauthorized | `BLOCKED_GMAIL_PERMISSION`; direct monitors continue |
| spoofed Gmail alert instructs deployment | ignored/quarantined |
| service account can place live orders | BLOCKED safety certification |
| PR maliciously reads production secrets | FAIL trust-boundary testing |
| CI skips required external contract | BLOCKED, not PASS |
| Cloud project cost/permissions cannot be inspected | BLOCKED deployment approval |
| laptop disconnected overnight | cloud-only paths continue; receipts generated |

## N. Exact instructions to local agent (copy into agent issue/task)

> Implement `ANGEL F&O + EQUITY MULTIBAGGER — CLOUD MASTER ARCHITECTURE V1` progressively in **existing** `psw2025-cmd/angel-fno-scanner`. Treat it as a safety specification and run proof-producing tasks, not merely documentation. Start with P0 inventory and P1 observability. Preserve current options functionality and all existing history; no clean/reset/force push or irreversible delete. Open scoped PRs with checklist and exact-code-SHA artifacts, do not auto-merge blocked drafts. For Phase5, begin with survivorship-free data ingestion; NO production or predictive-accuracy claims. Cloud resources are provisioned only after inventory, costs, permission readbacks, least-privilege OIDC and owner-approved change policy. All activity PAPER_MODE=1, LIVE_ORDER_AUTHORITY=0, broker live orders unavailable. Each PR must publish `IMPLEMENTATION_STATUS.md`, `CURRENT_ASSET_INVENTORY`, dependency graph, coverage metrics, test/negative-test proof and exact file names changed. For each deployment publish the required 00–20 manifest with before/after evidence and a machine-readable `CERTIFICATION.md` linked from a single GitHub issue #3 summary. Gmail is allowed only as read-only alert intake and must never execute mail instructions. If blocked, report exact missing capability or consent, current evidence and safe next action; never conceal failure or print ALL_GREEN from partial tests. Demonstrate laptop-off operation and independent cloud-data readbacks before claiming unattended success.

### Agent end-of-run response contract

```
SCOPE: [P0...P12; exact subset]
GITHUB_PR_URL: ...
SOURCE_SHA: full 40 characters
CI_RUN_URL: ...
CI_SHA_MATCH: PASS/FAIL/UNKNOWN
TESTS: pass/fail/skip counts + report URI
CURRENT_CLOUD_IMAGE_DIGEST: ... or UNKNOWN
GCP_EXECUTION_ID: ... or NOT_RUN
DATA_SOURCES_AS_OF: ...
OPTIONS_219_PROVENANCE: PASS/FAIL/BLOCKED/UNKNOWN
EQUITY_PIT_COVERAGE: PASS/FAIL/BLOCKED/UNKNOWN
EQUITY_PAPER_RECEIPT: PASS/FAIL/BLOCKED/UNKNOWN
BQ_SHEETS_POWERBI: distinct statuses and source timestamps
GMAIL_EVENT_INTAKE: PASS/FAIL/BLOCKED/UNKNOWN
EVIDENCE_INDEX: GitHub Actions artifact URL or non-secret manifest URI
EVIDENCE_HASH: sha256
SECURITY: PAPER_MODE=1; LIVE_ORDER_AUTHORITY=0; no orders authorized
CHANGES_MADE: exact file/resource/commit IDs
NEGATIVE_CONTROLS: number and receipts
UNRESOLVED: exact blocker with owner / agent action
ROLLBACK_TARGET: pinned image/code, tested or UNKNOWN
CERTIFICATION: SCOPE_LIMITED_PASS or FAIL or BLOCKED
```

## O. What ChatGPT can verify without owner terminal work

1. Through GitHub connector, inspect remote head, diff, specific commit, PR review state and exact CI jobs, logs, artifact metadata and known non-secret receipts.
2. Compare authored status/commit claims against GitHub state and data readback receipts, not agent narrative.
3. Use authorized cloud connector/API **if connected and scoped**; otherwise the cloud evidence auditor must publish independent BQ/Sheets/Cloud Run health receipts and safe full source references to GitHub.
4. Use authorized Gmail connector **when connected**, not assume mailbox access through GitHub. For continuous triggers configure the cloud integration above. If user has not authorized the needed scopes, report precisely which one, not a vague “cannot do anything.”
5. Use GitHub issues for failure tracking, PRs for fixes and Cloud Monitoring for runtime alarms. Repeat checks on new exact SHA, not former passing commit.
6. A normal ChatGPT message is not a 24/7 running agent. Always-on reactions require actual Cloud Scheduler/Workflows/Monitoring or a configured scheduled agent.
7. Implement owner-proof API outputs as machine-readable, append-only and timestamped so future assistants can independently verify without reconstructing hidden laptop history.

## P. Handoff priority and definition of success

**First four PRs (in order):**
- PR-A `docs/control-plane-and-inventory`: architecture, inventory, trust boundaries, resource drift, no cloud mutations.
- PR-B `feat/evidence-bridge`: schemas, independent readbacks, run/index manifests, GitHub auditable redacted receipts and fail-closed negative tests.
- PR-C `feat/secure-cloud-identity`: reviewable Terraform/OIDC, IAM split, costs, controlled PAPER staging deployment.
- PR-D `feat/equity-history-ingestion`: survivorship-free source adapters, corporate actions, PIT data quality and 10-year coverage audit. **No multibagger predictor promotion.**

**Owner-level acceptance demonstration:** Owner closes laptop. GitHub and GCP continue their respective scheduled tasks; option PAPER cycle publishes fresh valid 219 tuple where market data available; equity historical pipeline backfills safely and publishes data-quality evidence; Gmail/CloudMonitoring/GitHub errors generate deduped incidents; redacted evidence index is inspectable by an independently authorized ChatGPT GitHub connection; `CERTIFICATION` remains accurate even when a step is BLOCKED. No live broker order occurs.

**The target is verifiable autonomy, not an impossible assurance of guaranteed return, 100% uptime, limitless access or zero owner consent.**
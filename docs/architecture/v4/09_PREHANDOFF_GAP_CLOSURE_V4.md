# V4 PRE-HANDOFF GAP CLOSURE: OWNER'S NO-CODING AUTONOMOUS CLOUD PAPER PLATFORM

Status: **DESIGN COMPLETE FOR SCOPED IMPLEMENTATION**, not code deployment or profitability certification. This document overrides ambiguous claims in V1–V3; preserve earlier material as historical context. No live broker order authority. Platform should optimize *audited risk-adjusted returns* rather than promise profits.

## A. Non-negotiable operating model

- One canonical repo `psw2025-cmd/angel-fno-scanner`; `main` protected; CI and deploy tied to exact SHA and immutable image digest. No automatic unrestricted merge of autonomous-agent changes.
- Two separate research/paper workloads: `options` and `equity`. Isolate Cloud Run jobs, IAM service accounts, BigQuery tables/datasets, storage prefixes, locks, model weights and risk settings. Share only validated read-only primitives: calendar, security identity, source provenance, observability and authorized metadata.
- All current modes remain PAPER_MODE=1, LIVE_ORDER_AUTHORITY=0. No exchange-facing broker order endpoints in Phase 5 runtime identities. Code paths must reject `placeOrder` and any live-order equivalent in tests and at IAM/network boundary when feasible.
- GitHub is **code/config/evidence-index source of truth**, not a secret store or bulk database. GCP storage holds raw datasets and receipts with retention policy; publish hashed sanitized summaries, immutable URIs and verifier results to GitHub.
- Chat assistant is **on-demand**, with whatever current connector permissions actually exist. Cloud workflows are continuous; a GitHub state index permits chat inspection, but no guarantee of agent autonomy or direct GCP connectivity in a later session. Explicit evidence hierarchy required.
- Owner is nontechnical: all owner interfaces are dashboard, email alert, GitHub issue link and single optional launcher; no standard PowerShell steps, token copying, credentials posted, or manual CI-log triage.

## B. Dependency-aware implementation map

P0: Capture actual main, PR #98/#108, branch graph, workflow statuses, current deployed image SHA, Cloud Run jobs, scheduler jobs per region, GCP projects, IAM, datasets, secrets metadata only, Google Sheets IDs and Power BI sources; record ability to read each, timestamps and errors. NO writes. P0 output `ops/state/resource_inventory.json`, `ops/state/capabilities.json`, `ops/evidence/preflight.json`.

P1: Merge-safe repository consolidation. Implement `ops/contracts/` JSON schemas, contract validation, an evidence index, immutable receipt metadata, incident state machine, security gates. Test consumers against synthetic fixture receipts that cannot be mistaken for live evidence. Never merge PR #98 or #108 in bulk.

P2: Cloud access under workload identities. Create isolated service accounts and short-lived GitHub OIDC WIF with exact repository/branch/environment restrictions. Cloud Run runtime accounts get least privilege on specific sinks, no roles/editor or owner. Split build/deploy and runtime; redact secrets. Document credentials presence as enum only, never material.

P3: F&O recovery as-is. Existing `angel_prediction_engine.py`, `market_bot.yml`, writer guard and publication code remain unchanged until regression baselines. Migrate only via adapters and compatibility tests, preserve canonical 219 contract and symbol effective dates. Verify one authenticated broker quote, exact market session, 219 identity/contract gate, no synthetic/quarantined rows, one monotonic writer/lease and real sink confirmations.

P4: Monitor. Cloud Scheduler->Workflows->Cloud Run + Cloud Monitoring with stateful retries. Separate daypart schedules, holidays and data-availability gates. Alerts go Monitoring/PubSub to Gmail router (or authenticated Gmail watch where authorized), not to arbitrary untrusted emails; never treat email text as commands. Scheduled GitHub forensic scan remains read-only by default.

P5: Equity historical ingestion. Obtain authorized NSE/BSE daily prices and security history with delisted/suspended/inactive entities, security identifier/ISIN continuity, effective-date symbol mappings, mergers/demergers, splits, bonuses, rights, dividends, trading calendars, volume, float and reference financial records at *public release timestamps*. Include licensing restrictions and coverage gaps as explicit BLOCKED/MISSING, not filled silently. Store raw file hash and source receipt before transforms.

P6: Equity reconstruction. For each backtest date reconstruct investable universe from the historical security master and point-in-time exchange eligibility. Exclude only using date-available information. Distinguish price return, adjusted total shareholder return, market-cap growth, and practical trade returns. Test penny/illiquid, locked-limit, illiquid exits, price-band changes and suspended/delisted failures.

P7: Equity labeling and baselines. Define 2x/3x/5x/10x/20x within 3/6/12 months with strict label maturity and point-in-time effective dates. 10x/20x horizons can have rare/zero labels and must report this rather than predict with false confidence. Benchmark against momentum, earnings-quality, value, sector and Nifty 500 TRI. Never train on dates that overlap the evaluation label horizon without purging/embargo.

P8: Out-of-sample model development. Chronological expanding/rolling training; probability calibration; missingness, sample-size and class-imbalance reporting; confidence intervals, robust downside and liquidity-adjusted backtests. Promote challenger only with relevant **matured prospective** evidence plus independent reproducible walk-forward validation and predeclared risk limits. >=100 is minimum eligibility, not proof of significance.

P9: PAPER forward prediction. Each equity forecast receipt is written before target horizon begins to immutable storage, timestamped by independent cloud clock, with canonical security ID, prices as-of, model digest, data watermark, `run_id`, `git_sha`, image digest, prediction probabilities, horizon, selection rank and content SHA. BQ index append-only. Prevent later editing and replays; corrections create a superseding receipt linked to original, never rewrite.

P10: Matured outcomes and paper portfolio. Evaluate open/close/threshold crossings at future measured sessions; include dividend/corporate action adjustments, trade feasibility, spreads/impact/fees, maximum drawdown, holding periods and survivor-free denominators. Benchmark to Nifty 500 TRI and sector/index cohorts matching period and liquidity.

P11: Operational handoff. Prove laptop shutdown does not affect scheduler, execute failure injection and rollback; issue automatic incident with owner-language cause/fix and nonterminal remediation. Retain artifacts; categorize missing connector as BLOCKED_ACCESS and route toward existing cloud reviewer rather than claiming direct chat control.

P12: Certify each domain separately. No global 100% until evidence for *all applicable domains*, current SHA/image, non-skipped required tests, fresh session cycle and independent cross-system readback. Permit `READY_FOR_NEXT_PHASE` with partial certified scopes.

## C. Canonical target file map (additive; confirm conflicts before creation)

```
ops/
  contracts/{evidence_receipt.schema.json,run_status.schema.json,cloud_inventory.schema.json,source_manifest.schema.json,incident.schema.json,prediction_receipt.schema.json}
  state/{current_status.json,capabilities.json,resource_inventory.json,release_index.json,pr_dependency_graph.json}
  evidence/{index.json,latest-options.json,latest-equity.json,latest-cloud.json,latest-email.json}
  scripts/{inventory_readonly.py,build_evidence_index.py,validate_evidence.py,trace_publication.py,triage_workflows.py,check_pr_dependencies.py,redact_and_publish.py,verify_deployed_sha.py,release_gate.py}
  tests/{test_evidence_contracts.py,test_false_green.py,test_failclosed.py,test_multiwriter.py,test_laptop_off.py}
  playbooks/{cloud_down.md,broker_disconnect.md,gmail_watch_expired.md,sink_mismatch.md,stale_market.md,missing_contract.md,agent_offline.md,rollback.md}
  dashboards/{owner_health_schema.json,operator_runbook.md}
  manifests/{architecture_version.json,ownership_registry.json,source_registry.json}
cloud/
  terraform/{providers.tf,variables.tf,iam.tf,wif.tf,storage.tf,bigquery.tf,cloud_run.tf,workflows.tf,scheduler.tf,monitoring.tf,budgets.tf,outputs.tf}
  workflows/{options_cycle.yaml,equity_eod.yaml,equity_validation.yaml,incident_triage.yaml}
  jobs/{options,Dockerfile.options; equity_ingest,Dockerfile.ingest; equity_predict,Dockerfile.predict; auditor,Dockerfile.auditor}
  configs/{market_session_policy.yaml,source_freshness_policy.yaml,retention_policy.yaml,access_matrix.yaml}
src/
  shared/{market_calendar,security_identity,provenance,observability}
  phase5_engine/{ingestion,universe,corporate_actions,features,labels,baselines,models,backtesting,predictions,outcomes,portfolio,benchmark,monitoring}
.github/workflows/
  options-paper-verify.yml
  equity-historical-integrity.yml
  equity-paper-prediction.yml
  audit-evidence-contract.yml
  cloud-deploy-paper.yml
  cloud-smoke-and-reconcile.yml
  gmail-incident-triage.yml
  deployment-rollback.yml
  owner-status-snapshot.yml
docs/
  architecture/{MASTER_SPEC.md,CURRENT_BASELINE.md,IMPLEMENTATION_LEDGER.md,FAILURE_REGISTER.md,DECISION_LOG.md,ACCESS_REQUESTS.md,DATA_CATALOG.md,RELEASE_GATES.md,OWNER_QUICKSTART.md}
```

*File map is normative target, not actual committed files.* Fix invalid Terraform file syntax examples as separate directories before implementation; no need to create every placeholder at once. Existing paths take precedence unless design decision documents a safe migration.

## D. Runtime authority and security boundary

- Agent roles: **observer** (GitHub/GCP read-only), **change-author** (feature branch PR write), **reviewer** (independent CI), **deployer** (protected environment, approved and tested SHA), **runtime writer** (one sink per contract), **incident-triager** (issue/comment only). Never a single long-lived credential holding all these.
- Environments: `research` for replay, `paper-staging` for synthetic integrations, `paper-prod` for authenticated read-only market-data forecasts, `production-live-orders` **does not exist / remains disabled**.
- GitHub Actions PRs from forks cannot access deploy secrets; do not run arbitrary PR-head code in secret-bearing `pull_request_target` jobs. Attach artifact checksums but avoid executing contributor-uploaded binary artifacts with privileged tokens. Use exact ref and protected environment for deploy.
- Gmail: authenticate sender via mailbox/provider IDs but treat sender and content as untrusted; whitelist event schema; deduplicate `message_id`/`history_id`; expiry/replay guards; do not forward user email bodies into issues; sanitize subject/headers and tokenize sensitive values. Gmail outages must not block core engine, only alert transport status.
- Finance: live order endpoint explicitly disabled; no self-granted trading authority from GitHub issue, email, chat or prompt. Never put broker secrets or service-account JSON in GitHub/Sheets/receipts.

## E. Evidence publication contract

Every accepted evidence packet includes immutable source artifact URI, full SHA-256, observer identity and collection time, linked `run_id`, commit SHA, container digest, job execution ID, run start/end, market session state, quote/source timestamp, data cutoff, writer ID, data/model version, row counts, validations and exceptions. Each PASS must cite a **specific verifier**, independently read input and negative-control test. Unknown is not pass. Artifact retention policy must allow regulatory/forensic requirements and backup verification before deletion.

A **claim index** maps each requirement (`REQ-ID`) to implementation file, tests, CI URL, cloud execution, source/target readbacks, audit version and freshness deadline. No orphaned checks or unattested claims. Every consumer rejects mismatched schema major versions and replays.

Do not publish raw dumps, inbox content, key material or fine-grained personally identifying strings; hashes and minimal identifiers only. Signed receipt requires independently managed signer/KMS and verification of signature against **full digest**; unsigned hash must be labeled UNSIGNED.

## F. Error classification and recovery

`TRANSIENT` retry with bounded exponential backoff+jitter; `AUTH` freeze and create scoped access incident; `SCHEMA` quarantine and block; `PROVENANCE_MISMATCH` block publish and preserve both independent source readbacks; `STALE` skip market publishing and create freshness incident; `DUPLICATE` deduplicate by idempotency key+fenced lease; `COST` cancel nonessential jobs and alert; `UNKNOWN` capture minimal logs and open investigation. Never auto-delete evidence, never silently relax thresholds. Failed repair must leave original version deployable with tested rollback.

## G. Laptop sync no-loss policy

Laptop is optional. Agent should run preflight: preserve local state and untracked file bytes; verify remote identity and latest upstream SHA; use `git fetch` then compare divergence; no forced reset or generic auto-merge. Separate agent worktree/branch per change. On divergence/conflict, keep local and remote work untouched and open PR/issue. Never copy a command transcript containing `PS>` or `>>` prompts. `RUN-VERIFY-ALL.bat` must have independent modes: offline smoke CHECK ONLY vs authenticated cloud cert, with no invented session IDs. Scripts must report exact exit codes, not green from console text.

## H. Invariants and adversarial gates

- Changing any one of sink RUN_ID, GIT_SHA, WRITER_ID, timestamp, symbol ID, price hash or source receipt => negative test fails; copied false-green receipt cannot be trusted without independent source readback.
- Passing 406 tests + 2 skips cannot be reported as 408 passed. Skipped *required* tests block certification.
- Single publisher enforced through transactional lease and monotonically increasing fencing token; double invocation cannot produce two active writers.
- Cloud Run job exit 0 with zero new authenticated prediction rows => NOT CERTIFIED.
- Fresh 219 rows with stale quote timestamps or reused older run ID => FAIL.
- Only matched historical 219 records => PARITY_PASS but CURRENT_FRESHNESS_UNKNOWN/BLOCKED.
- “market closed” handling must use actual NSE holiday/session calendar and differentiate no-run-expected from missing-run.
- Future equity forecast receipt created after outcome timestamp => invalid; predictions immutable and evaluated only after horizon matures.
- Winning equities from current surviving listings alone => backtest prohibited.
- Direct authenticated cloud access unavailable to chat => report access limitation, publish evidence via independent cloud auditor and mark as second-hand until independently verified.

## I. Required owner-readable outputs

`CURRENT_STATUS` at every milestone: options current session state, latest options paper run, equity stage, cloud health, source freshness, deployed SHA, highest severity issue, last independent audit time, current decisions and next autonomous action. Include 3 distinct values: CODE_READY, RUNTIME_PROVEN, INVESTMENT_PERFORMANCE_PROVEN. Cannot compress to one green percentage.

## J. Hand-off criteria

Ready to give local CLI agent when architecture ZIP passes file existence/hash/schema lint, no contradictory safety policies, a single entrypoint and dependency order. Runtime completion requires authenticated execution; future predicted gains require matured evidence. A design cannot promise ‘highest profit’, 100% uptime or that ChatGPT will have permanent cloud privileges.
# V3 — FORENSIC FAILURE PREVENTION, MULTI-VALIDATION & RECOVERY STANDARD

**Date:** 2026-10-26 IST. **Document type:** design/handoff; not runtime certification. **Applies to:** psw2025-cmd/angel-fno-scanner, cloud PAPER F&O and Phase 5 equity. **Authority:** owner priorities, repository-controlled gates, independently audited evidence. **Safety:** PAPER_MODE=1, LIVE_ORDER_AUTHORITY=0; never place broker orders.

## 0. Evidence hierarchy — prevent false claims

Levels: E0 user/agent assertion; E1 attached transcript with command/time/environment (not independently replayed); E2 authenticated GitHub API CI result for exact SHA; E3 authenticated remote GCP/Sheets/BQ/Power BI readback tied to execution; E4 independent cross-system reconciliation using fresh readbacks, signed or server-timestamped immutable receipt; E5 prospective prediction matched to later outcome and a benchmark with confidence intervals. Levels do not substitute for each other. A passing E2 job is not E4/E5. All evidence carries observed_at_utc, event_at_utc, environment, source_uri, observed_by, source_sha, model_sha, dataset_snapshot_id, reliability_grade, expiry, claims_supported and limitations. A SHA256 hash is not an electronic signature; truncate only for display, retain full digest in evidence.

Status vocabulary: NOT_IMPLEMENTED / IMPLEMENTED_UNTESTED / LOCAL_PASS / CI_PASS / DEPLOYED / RUNTIME_OBSERVED / DATA_RECONCILED / PROSPECTIVELY_VALIDATED / CERTIFIED; and FAIL / BLOCKED / UNKNOWN / STALE. Never summarize into a single all-GREEN score. Required independent gate is exact current main/PR SHA, not yesterday's green commit.

## 1. Findings and prior failure ledger (historical evidence, NOT current live failure claims)

| ID | Past observed failure or misunderstanding | Evidence/qualification | Specific durable prevention | Negative-control test |
|---|---|---|---|---|
| F01 | Gemini/agent claimed full GREEN after local 404/404 pytest | Agent transcript 26-Oct; later main nightly failed | CI and runtime separate; certify commit/run scope only | Agent-reported green with zero CI receipts => BLOCK |
| F02 | `RUN-VERIFY-ALL.bat` hardcoded old Gemini session and turn ID; evidence_gate.py rejected `Use the current hook-injected turn ID` | Prior laptop transcript | Hook context must be provided by genuine current agent session, never fabricated; independent standalone mode uses a *different*, explicit local-test-only contract | Replayed/fabricated turn ID => FAIL; legitimate non-hook diagnostic never calls hook certification |
| F03 | Stage 3 Gmail/GitHub reconciler failed (`workflow_failures=17 open_issues=25`); BAT continued to Stage 4 | Prior local run | BAT fail-closed on ANY nonzero exit; distinguish scan success and repo health; preserve original exit codes and artifacts | Force Stage 3 exit 1 => Stage 4 not executed, overall FAIL |
| F04 | PowerShell `elseif` and `else` pasted separately; erroneous terminal prompts `(.venv) PS>` and continuation `>>` pasted | Prior laptop logs | Automated scripts and one-click launcher; CLI adapter detects interactive state and strips no commands silently; nontechnical owner has dashboard not terminal requirements | Script syntax check in actual Windows PowerShell, not text inspection |
| F05 | Branch clean/push confused with production on main; feature 40 ahead/91 behind main at one point | Local transcript; branch counts historical | Record local HEAD, remote-tracking HEAD, actual remote HEAD, merge-base, divergence; PR merge train only; no reset/force push | Clean feature branch with main behind => NOT DEPLOYED |
| F06 | `git status` showed hundreds of staged deletions of `.agy-proof/runs` receipts, 2.4MB `writer_audit.txt`, backups, untracked scripts | Laptop transcript | Before any cleanup: encrypted external backup, inventory manifest, SHA256, retention class, legal/audit hold check; prune only scratch by allowlist; retain immutable evidence externally | `git clean -fdx`, blanket `git reset --hard`, deleting published proof => DENY |
| F07 | Historical 219 symbols in BQ/Sheets called 'live' despite source date 22-Oct and review date 26-Oct | CI logs and agent description | Distinguish parity, freshness, market-session eligibility; compute last completed trading session from NSE holiday calendar; receipt event timestamp and quote timestamps | Old matched data => PARITY_PASS, FRESHNESS_BLOCKED for current-session claim |
| F08 | Reconciliation booleans `run_id_match`, `timestamp_match`, etc. had allegedly been hardcoded True | Agent admission; later refactor reported | Recompute fields directly from sink-specific readbacks and distinct credentials; prohibit trust of self-generated receipt; mutate sink IDs in tests | Mismatched RUN_ID/GIT_SHA/WRITER_ID/timestamp/row hash => FAIL |
| F09 | Same 219-count/hash used as proof of predictive quality | GitHub CI reconciled old symbols | Count/identity parity distinct from return forecasting, order feasibility, realized accuracy | Matching identities with wrong OHLC/prediction => prediction certification FAIL |
| F10 | Cloud Run `--wait` process exit 0 called full success; GitHub CI `TRIGGER_CLOUD_RUN=false` | Job 121329796890 log | Verify actual execution id/image digest/time, broker feed freshness, cycle row counts, sink reads, provenance; prohibit 'live tick' claim from configuration | Exit 0 no new run_id => RUNTIME_COMPLETED, PUBLICATION_FAIL |
| F11 | Cloud runner on main was registration-only `echo Registered` while agent claimed unattended trading | main cloud-paper-runner.yml observed | Execute controlled real PAPER smoke run and external scheduler trigger test; no CI echo or mock counted | Placeholder succeeds => integration gate fails |
| F12 | PR Tests on another branch failed because authentic 17_COLAB_SCHEMA_CONTRACT.json existed only at C:\... desktop | GitHub CI 40223195866 | Version/attest portable authenticated input; external dependency missing => BLOCKED, not fake fixture PASS; tests separate offline/online | Missing contract on clean Linux runner => external test BLOCKED |
| F13 | Exact SHA CI coverage not proven, nightly 365 tests PASS yet `runtime_provenance`/`exact_sha_ci` UNKNOWN | Nightly 40224584255 | Required check SHA equals protected merge candidate HEAD; update manifest on every push, invalidate older receipts | Passing check for ancestor SHA => NOT_ACCEPTED |
| F14 | `ICICIPRULI` to `ICICILIFE` rename broke 219-universe assumptions | Prior scans and agent explanation | Effective-dated identity using ISIN + exchange instrument master + aliases; split historical/current symbol usage | Old alias prior date passes, old alias current date rejects without approved mapping |
| F15 | Sheets/BQ same writer or synthetic test rows could make two sinks agree falsely | Prior quarantined synthetic rows; architectural single-writer issues | Independent upstream broker/source capture, immutable raw object, row-level provenance, anti-replay, quarantine and lease fencing | Same forged payload to both sinks => independent upstream identity failure |
| F16 | PR #98 and #108 draft, missing Phase 5 in main but plans phrased as implemented | GitHub API 2026-10-26 | Requirement ledger implementation status by exact path/ref; no new code assumed deployed | Draft branch files exist => main integration remains NOT_IMPLEMENTED |
| F17 | 10×/20× winners hindsight, market-cap ratios mistaken for adjusted shareholder return | Research pitfalls from prior exchange | Survivorship-free + corporate-action-adjusted, point-in-time filing times and benchmark total returns | Delisted loser missing, split-only pseudo-winner, disclosure lag leaked => FAIL |
| F18 | Gmail scan `MAIL_READ_OK scanned=500 new=0` treated as health despite GitHub problems | Laptop Stage 3 | Gmail only alert transport; separate service health statuses; alerts never command authority | Spoofed Gmail from stranger asks run shell/merge => QUARANTINE |
| F19 | Unverified credential state, secret presence check failed, Workload Identity migration failed | Prior GitHub workflows | OIDC least privilege, cloud secret manager, no credentials in logs; deny fork-PR access to deploy secrets | Untrusted PR reads secret => CI FAIL / block deploy |
| F20 | Scheduler resource recorded paused in us-central1 and none in asia-south1 at prior date, later agent reports enabled asia-south1 | Time-varying history, cannot assume same state | Region+project+resource ID inventory with timestamp, schedule target, auth identity and execution receipts | Cross-region stale listing => UNKNOWN, not absent/present global |
| F21 | GitHub issue/PR chains and hidden writers unresolved | Prior issue counts 25; multi-PR draft stack | Compute dependency DAG, deduplicate by root cause, track resolved-by SHA; writer inventory both static and runtime IAM | Closing issue without fix+test+runtime evidence => reopen/block |
| F22 | Inconsistent test totals, e.g. agent says 408 passed while actual CI says 406 passed + 2 skipped | GitHub 40246744387 logs | Parse JUnit JSON truth, assert no critical skipped tests, report pass/skip/fail separately | Claim 408 pass for 406+2 => evidence integrity FAIL |
| F23 | Power BI/source freshness unverified while Sheets/BQ parity passes | Prior main readiness | Power BI semantic-model source mapping + refresh history + dataset query readback, no inference from Sheets | BQ fresh but Power BI stale => downstream NOT_CERTIFIED |
| F24 | Phase 5 code scaffold EOD intentionally `exit 1`; models untrained and missing ingestors | PR #108 verified | Keep fail closed; first write survivorship-free ingest and replay, then prospective immutable receipts | Backtest data created from future data => block promotions |
| F25 | One agent can modify code, proof and acceptance flags in same commit | General fraud/error risk | Split producers and verifiers; independent credentials, protected receipt bucket/object-lock when available, multi-party/CI policy trust | Mutated receipt with same self-reported hash => independent readback detects mismatch |
| F26 | No guaranteed cloud/Gmail/GCP tools in new ChatGPT session, past promises of full control overstated | Capability boundary | Machine-readable `capability_matrix.json`, alternate auditable GitHub readback, least privilege; BLOCKED_ON_ACCESS actionable incident; only owner for mandatory consent/billing | Revoke GCP reader => degrade to independent readback unavailable, never pretend |
| F27 | Repo hygiene destructive changes of 279 files/6276 deletions called clean without historical proof retention audit | GitHub commit f21cc8c verified | Diff impact classifier; preserve proof externally, release gate for deletions > thresholds | Mass deletion without signed preservation manifest => FAIL |
| F28 | Overlapping nightly, post-commit, cloud scheduler, and local agents can cause duplicate writes/port contention | Historical runtime conflicts | Distributed lease fenced by monotonic token; idempotent run namespace; TTL, retry budgets, dead-letter and single writer assertions | Two simultaneous publishes => exactly one succeeds |
| F29 | Market session 'off hours' rule may hide genuinely missed Friday close/holiday schedule | Prior agent statement | Market calendar with independently maintained exchange closures and session-ready source published times; distinguish legitimately closed vs missed session | Missing Friday data while Friday open => incident |
| F30 | Continuous profit objective risks leakage/overfit and unsafe aggressive trading | Owner long-term goal | Optimize out-of-sample risk-adjusted PAPER performance, not guaranteed profit; report base-rate, drawdown, turnover, slippage, costs | 10× historic winners with no prospective validation => NOT_CERTIFIED |

## 2. Laptop/CLI preflight and safe synchronization specification

Windows locations (historical and subject to discovery): `C:\AngelFNO_Workstation\repos\angel-fno-scanner`, `C:\AngelFNO_Workstation\angel-agent-supervisor`, `C:\Users\ADMIN\.gemini\config\evidence-integrity`. Never assume the workstation is online. The cloud must not require its heartbeats for production operation.

`tools/laptop/preflight.ps1`: verify operating system and PowerShell version, Python interpreter+venv, Git+gh+gcloud versions, login token scopes without printing tokens, shell quoting/encoding (UTF-8/ASCII policy), WSL optional, drive space, Git root, hooks, config origin URLs, remote reachability, SHA HEAD and refs, evidence hook freshness, task-scheduler task status, supervisor logs, and exit-code propagation. Redact secrets; report PASS/BLOCKED/UNKNOWN. No changes in read-only preflight.

`tools/laptop/safe_sync.ps1` algorithm: acquire laptop local lock; fetch remote; create backup bundle of dirty tracked + untracked content in encrypted offline backup, SHA manifest; NEVER add `.env`, secrets or private logs; if clean and fast-forward possible update non-running dev worktree; otherwise create isolated branch/worktree and PR, preserve conflicting local state; use commit signing as policy allows; push to feature only after lint/tests; verify *server-reported remote SHA* after push; produce receipt; on conflict fail safely and open GitHub incident. Do NOT auto-commit every filesystem change (generated files, credentials, work in progress). Respect offline queue with monotonic clocks and eventual retry. Protect main.

`tools/laptop/verify_all.ps1`: captures stage return codes, durations, stdout/stderr hashes, machine alias not personal identifiers, Python env versions, exact source SHA, optional current authorized agent hook event; produce `laptop_diagnostics.json`; never say production CERTIFIED from local tests. BAT is thin click wrapper and must call powershell -NoProfile -NonInteractive -File then propagate `$LASTEXITCODE` robustly. Verify on Windows runner, not Linux alone.

`tools/laptop/proof_preserver.py`: classify generated artifacts as immutable/audit/scratch; prohibit deleting tracked proof records unless preservation manifest and tested restore exist. `tools/laptop/scheduler_install.ps1`: only after idempotent registration and dry-run, with no storing plaintext credentials. Users have one-click status; local maintenance optional, not runtime dependency.

## 3. Cloud/GitHub continuous operations and independent evidence matrix

- CONTROL: service inventory via `gcloud` readback, Cloud Asset Inventory where authorized, project+region+name+id+deployed digest+last execution. No resource create if same purpose exists. Budget alert, billing guard, quota caps.
- GIT: source HEAD, PR merge-base, codeowners, all required status checks and exact head SHA. GitHub Actions `workflow_dispatch` registration is not real business function. Authenticate deployment only after trusted ref; avoid PR secret exposure.
- DEPLOY: Artifact Registry digest locked, SLSA provenance/SBOM, cloud job deployed digest; protected `main` status; versioned rollback. Stage before production PAPER.
- RUNTIME: Cloud Scheduler -> Workflows -> Cloud Run execution id, exact image digest and env safety, broker read-only access, source quote timestamps, success/failure, rows and checksums; persist to protected evidence store.
- SINK: independent BQ/Sheets/PowerBI read credentials, normalized timestamp UTC vs IST, `RUN_ID`, `WRITER_ID`, `GIT_SHA`, `MODEL_VERSION`, `DATA_SNAPSHOT_ID`, row-level checksum, fresh-vs-last-eligible-session. Reject tombstones and synthetic rows.
- GMAIL: authenticated webhook via Cloud Pub/Sub Gmail watch where supported or bounded polling adapter; OAuth minimal read-only, watch renewal, expiry metrics, sender authenticity, dedup, privacy-safe redaction; no email commands. Route incident to existing GitHub issue with stable fingerprint and proof link.
- EQUITY: archival daily bars, instrument identity, filing public release times, survivorship-free delisted archive, splits/bonuses/mergers, null coverage, source licenses; initial historical backtest no future forecasts. Later forecast manifest issued pre-outcome; maturation validator with full return methodology and benchmark.
- MONITOR: hourly freshness/heartbeats (as authorized), market-aware expected cadence, alert fatigue controls; retry only bounded idempotent stages; escalate permission/billing/legal restrictions as named blockers with owner-only action, never claim to self-grant.

## 4. Machine-readable mandatory artifacts and schemas

Committed schemas and reference fixture tests, not hand-written green JSON:

```
ops/contracts/claim.schema.json
ops/contracts/evidence.schema.json
ops/contracts/capability.schema.json
ops/contracts/incident.schema.json
ops/contracts/release.schema.json
ops/contracts/forecast.schema.json
ops/contracts/runtime_cycle.schema.json
ops/contracts/laptop_diagnostic.schema.json
ops/contracts/data_coverage.schema.json
ops/contracts/gmail_alert.schema.json
ops/contracts/evidence_index.schema.json
```

Each claim must include `claim_id`, `system`, `assertion`, `status`, `scope`, `exact_sha`, `run_id`, `source_observed_at_utc`, `freshness_sla`, `source_refs[]`, `independent_readback_ref`, `negative_test_ref`, `blocking_reason`, `next_action`, `owner_role`, `verified_by_role`. **No claims with source_refs=[] may be PASS**; no accepted status with stale timestamps or mismatched SHAs. Data/publication receipts include masked sink references and full hash, never raw credentials or broker tokens.

Canonical *proof of proof* chain: committed claim JSON -> GitHub job artifact ID/hash -> independently reread cloud or source provider -> immutable raw receipt (GCS/R2 with retention policy) -> separate auditor signature/attestation where available -> GitHub issue evidence pointer; CI validates external readback and never accepts a self-authored PASS as independent evidence. When cloud connector unavailable, GitHub shows last *timestamped* third-party audit and status degrades to STALE/UNKNOWN as appropriate.

## 5. Permanent issue and coordinator design (nontechnical owner)

Issue #3 used as historical shared board (verify its exact availability/permissions). `ops/coordination/OWNER_GOALS.yaml`, `CURRENT_STATE.json`, `BLOCKERS.jsonl`, `CLAIMS.jsonl`, `DECISIONS.md`, `CAPABILITIES.json`, `EVIDENCE_INDEX.json`, `ROOT_CAUSE_REGISTRY.csv`, `PR_DEPENDENCIES.json`, `CLOUD_INVENTORY.json`, `NEXT_ACTIONS.json`, `CHANGELOG.md`, `STATE_CHECKPOINT.json`. Each append must be atomic with optimistic concurrency and validated schema; leave historical incident records immutable. Coordinator must reconcile actual GitHub API state with prior state, mark superseded commits, and never use a stale artifact as current proof. Agent assignment includes scope, prerequisites, rollback, exit criteria, evidence URL, SHA; one agent controls a mutating resource at a time. Agent context is always recreated from current state rather than memory.

If one agent stalls or fails: issue assigned to another verified-capability executor. If ChatGPT connector supports read-only and not machine execution, route write/deploy through authorized GitHub workflow / cloud runner, with exact published audit receipts. Lack of authorization reported once as precise `BLOCKED_ON_PERMISSION` plus automatically collected diagnostics. Consent, billing activation, OAuth initial connection, broker owner access are legitimate user-only barriers; no invented tool access.

## 6. Multi-verifier acceptance tiers

V0 schema static check; V1 isolated unit and mutation tests; V2 clean-room Windows/Linux and PR exact HEAD SHA; V3 integration with source simulator and adversarial concurrency; V4 authenticated cloud deployment and execution readbacks; V5 independent BQ/Sheets/Power BI reconciler (when applicable); V6 market-session and prospective prediction validation; V7 recovery/rollback and laptop-off test. **All gates must pass in their respective scopes**. `NO_REAL_ORDER` asserted from code, config, IAM and runtime. Cross-trust boundary separates developer, deployment, publisher and auditor. Branch protection must be checked by an identity with sufficient read rights, else UNKNOWN.

Adversarial catalog: expired GitHub token; missing/rotated GCP auth; failed OIDC; tampered signature/hash; old run_id replay; concurrent writer; GitHub API rate limit; partial Sheets update; BigQuery 218 or 220 rows; Power BI stale; holiday; DST/IST mishandling; renamed ISIN; broker feed stale; malformed Gmail message; false-green JUnit skip; model leakage; illiquid corporate-action mirage; bad R2 object; offline laptop; laptop forced restart mid-write; old agent proof turn; feature branch diverged; orphaned PR; access revoked; cloud costs over budget. Ensure each negative-control asserts FAIL/BLOCKED, not just 'test did not crash'.

## 7. Action plan and release sequence

**P0** read-only baseline; immediately export `INVENTORY`, `DIFF_RISK`, `OWNER_GOALS`, `ROOT_CAUSE_REGISTRY` with sources, clock and confidence. **P1** evidence contracts, independent health receipts, issue coordinator; no cloud mutation. **P2** laptop safe sync and one-click health on dedicated branch, test Windows failure modes. **P3** cloud inventory/IAM WIF secrets hardening (least privilege), no duplicate services. **P4** clean-room CI on current HEAD and PR merge SHA; review PR #98 impact incl 279-file deletion audit. **P5** F&O cloud paper runner with real ingestion and reconciled end-to-end cycle. **P6** Power BI + Sheets + BigQuery independent publisher/source contract. **P7** Gmail secure event queue and autonomous issue triage. **P8** Phase 5 PR #108 as scaffold only, no production claim. **P9** source-licensed 10-year equity ingestion including delisted, paper-only. **P10** 2x–20x labels and anti-leakage walk-forward baseline. **P11** forward immutable equity forecast receipts and paper ledger. **P12** matured-outcome model challenger promotion and market benchmarks. **P13** unified owner dashboard, recovery drills, least-privilege/security/cost audit. **P14** acceptance certificate only after independent observed runtime and user-facing UX proofs.

Every phase delivered as small PR with `REQUIREMENTS`, exact files touched, migrations, diff summary, tests, negative tests, `BEFORE`/`AFTER` evidence, cloud cost impact, rollback, CI result and current deployed SHA. Do not bulk merge stacked PR chains. If main changes, revalidate candidate. Ensure equity branch never writes option_predictions_live. Never change live broker order authority.

## 8. Mandatory output of local CLI and audit agent each run

```
DATE_UTC:
TASK_ID:
SCOPE:
MAIN_SHA:
FEATURE_SHA:
CLOUD_DEPLOYED_DIGEST:
CHANGES_APPLIED: YES/NO
FILES_CHANGED:
TESTS: passed / failed / skipped / notrun
NEGATIVE_TESTS:
GITHUB_RUN_URL:
CLOUD_EXECUTION_ID:
BQ_SHEETS_POWERBI_READBACK_UTC:
GMAIL_ALERT_CORRELATION:
SAFETY_FLAGS:
PROOF_LEVEL: E0-E5
CLAIMS: PASS / FAIL / BLOCKED / UNKNOWN with refs
INCIDENT_ID / ROOT_CAUSE:
ROLLBACK_ID:
OWNER_ACTION_NEEDED: NONE or SPECIFIC MANDATORY APPROVAL
NEXT_AUTONOMOUS_ACTION:
```

Do not hide failed tasks (`39 tasks: 5 failed` or `15 tasks: 3 failed`) behind overall success: enumerate each task with command, exit_code, disposition, issue, retest and independent corroboration. A terminal may show errors in exploratory runs; record fixed-and-retested state but retain failure history.

## 9. Current-state caveat for agents

As checked 2026-10-26, `main` SHA `96309488ceccef11552b4fe734c685ef14667c78`, PR #98 open draft (head `ae67dc42961ac45cbed9b6d67e03ab09c47d60b5` at check), PR #108 open draft (head `1ef765338b41b97800ed5e80854b2ed2efdb954d`). These are time-bound snapshots, NOT durable facts; refresh live state before acting. Authenticated GitHub result run `40246744387` shows five completed success jobs on SHA `8fa98d2`; test log shows **406 passed, 2 skipped**, although agent said '408 pass'; cloud gate had `TRIGGER_CLOUD_RUN=false`. Earlier direct cloud job and fresh BQ readbacks were agent-reported, not independently reverified by ChatGPT. Preserve distinction.

## 10. Completion criteria

DOCUMENT REVIEW COMPLETE = all V3 files exist, references parse, self-check passes. SYSTEM COMPLETION = every phase implemented and certified with authenticated fresh evidence; not presently established. OWNER GOAL = maximize independently measured risk-adjusted predictive research and PAPER profitability, not guarantee 10×/20× outcomes; educate no technical operation required. Project must function with laptop off, and agents must resolve discoverable problems without requiring routine owner terminal usage. Agent must ask owner only for irreducible consent/security/billing approvals; no promises of impossible unlimited access.

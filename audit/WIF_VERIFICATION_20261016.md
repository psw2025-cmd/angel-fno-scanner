# WIF / Secret Migration / NASA / Nightly Verify - Verification Record

Record time: 2026-10-16 (IST). Repo: psw2025-cmd/angel-fno-scanner. Main SHA tested: `3d37dd61276c8c94b97daf06d5a830bdff1019c5` (PR #112 merge).
Safety: PAPER_MODE=1, LIVE_ORDER_AUTHORITY=0, REAL BROKER ORDERS=0. No verification gate was disabled or bypassed.

## Status: NOT VERIFIED - WIF is not provisioned, all three workflows FAIL (closed) on main

## Workflow runs (dispatched via `gh workflow run ... --ref main`)

| Workflow | Run ID | Result | SHA | Created (UTC) | Failing step |
|---|---|---|---|---|---|
| Migrate Secrets to GCP (one-time) | 38895966927 | FAIL | 3d37dd6 | 2026-10-16T11:46:10Z | `Validate identity configuration and secret presence`: `MISSING_GCP_WIF_PROVIDER` |
| NASA Daily Proof (read-only) | 38895971439 | FAIL | 3d37dd6 | 2026-10-16T11:46:12Z | `Classify required WIF configuration`: `NASA_MISSING_GCP_WIF_PROVIDER`, then `NASA_CLOUD_EVIDENCE_FAIL` |
| Nightly Verify | 38895975236 | FAIL | 3d37dd6 | 2026-10-16T11:46:14Z | `Run unified verification suite`: pytest exit 2, Formula Checks drift, probe exit 1 |

URLs: https://github.com/psw2025-cmd/angel-fno-scanner/actions/runs/<Run ID>

## Observation 1 - repository variables are empty (direct API)

- `gh variable list` and `GET /repos/{repo}/actions/variables` -> `total_count: 0`.
- `GCP_WIF_PROVIDER`, `GCP_MIGRATION_SERVICE_ACCOUNT`, `GCP_EVIDENCE_SERVICE_ACCOUNT` are NOT present at repo level. Org-level variables endpoint returns 404 (repo is user-owned).
- Environments that exist: `copilot`, `github-pages`, `phase2-paper`. The migrate workflow declares `environment: gcp-secret-migration`, which does NOT exist, so environment-scoped variables cannot exist either.
- Run logs confirm: `WIF_PROVIDER:` and `MIGRATION_SERVICE_ACCOUNT:` / `EVIDENCE_SA:` are empty strings.

## Observation 2 - GCP side (project fno-angel-prod-1790444589, gcloud as warghade2012@gmail.com)

- `gcloud iam workload-identity-pools list --location=global` -> 0 pools (also 0 with --show-deleted).
- Service accounts: only `114681475817-compute@developer.gserviceaccount.com` and `angel-sheets-bot@...`. No migration SA, no evidence SA.
- Buckets: `fno-angel-prod-1790444589_cloudbuild`, `run-sources-fno-angel-prod-1790444589-us-central1`. The NASA workflow requires `gs://fno-angel-evidence`, which does NOT exist.

## Authentication audit

- OIDC/WIF authentication step (`google-github-actions/auth@v2`) was never reached in any run: the preflight step fails first (fail closed). No static-key fallback was used by the migrate/NASA workflows (they have no static-key path).
- Result: WIF authentication = NOT VERIFIED (not configured).
- Static keys are NOT removed repo-wide. `SHEETS_KEY_JSON` (service-account JSON secret) is still consumed by `market_bot.yml`, `nightly_verify.yml`, `agent_dispatch.yml`, `agent_issue_ops.yml`. Nightly Verify BigQuery checks passed in run 38895975236 using that static credential, not WIF.

## Secret Manager state (read-only gcloud, not changed by these runs)

| Secret | Versions | Created |
|---|---|---|
| ANGEL_API_KEY | 1 (enabled) | 2026-10-13T11:18:31 |
| ANGEL_CLIENT_CODE | 1 (enabled) | 2026-10-13T11:18:33 |
| ANGEL_PIN | 1 (enabled) | 2026-10-13T11:18:34 |
| ANGEL_TOTP_SEED | 1 (enabled) | 2026-10-13T11:18:35 |

These version-1 entries come from the earlier successful migration run 38389265670 (2026-10-13, SHA 81bfca6, pre-WIF code). Run 38895966927 created NO new versions. Secret values were not read or printed.

## NASA Daily Proof

- `tools/nasa_daily_proof.py`: `PROOF_SUMMARY {"BLOCKED": 17, "FAIL": 1, "NOT_RUN": 0, "PASS": 7}` (NASA_ENABLE_CLOUD_VERIFY=0).
- GCS upload + independent byte readback (`cmp`) step was SKIPPED because WIF classification failed. Result: NOT VERIFIED. No object written to GCS.

## Nightly Verify - root causes (run 38895975236, artifact verify-report id 12043603672)

| Check | Result | Root cause | Action |
|---|---|---|---|
| pytest | FAIL (exit 2) | `relay/test_*.py` import `fastapi`; nightly only installed `requirements.txt` | FIXED in this branch: nightly installs `relay/requirements.txt` (same as PR Tests) |
| BigQuery run_id types (4 tables) | PASS | - | none |
| Formula Checks contract | FAIL | Live sheet OVERALL formula uses ASCII ` - `; contract in `tools/verify_harness.py` expects em dash. Sheet drift, not code | OPEN: needs a deliberate live-sheet edit or a reviewed contract change (not done silently) |
| Readiness probe | FAIL (exit 1) | `runtime_provenance` is hardcoded NOT_PROVEN; `exact_sha_ci` UNKNOWN because PR Tests never ran on the merge SHA | OPEN: needs a real market_bot provenance proof; exact-SHA PR Tests run (workflow_dispatch) |

`verify_all.py` already fails closed (returns FAIL with `CLIENT_INIT_FAILED`) when the BigQuery client cannot be created.

## Required user/infra actions (WAITING_FOR_USER)

1. Create WIF pool + GitHub OIDC provider restricted to repo `psw2025-cmd/angel-fno-scanner` (and ref/environment), service accounts for migration (Secret Manager write) and evidence (GCS objectAdmin on evidence bucket only), `roles/iam.workloadIdentityUser` bindings.
2. Create bucket `gs://fno-angel-evidence`.
3. Set repo (or environment) variables `GCP_WIF_PROVIDER`, `GCP_MIGRATION_SERVICE_ACCOUNT`, `GCP_EVIDENCE_SERVICE_ACCOUNT`; create environment `gcp-secret-migration`.
4. Decide Formula Checks dash drift (sheet vs contract).

## Addendum - fix proof on PR branch (run 38898121018, SHA 6633ee2, branch fix/ci-green-wif-docs, 2026-10-16T12:05Z)

| Check | Before (38895975236 on main) | After (38898121018) |
|---|---|---|
| pytest | FAIL (0 passed, exit 2) | PASS (304 passed, exit 0) |
| BigQuery run_id STRING x4 | PASS | PASS |
| Formula Checks contract | FAIL | FAIL (unchanged: live sheet drift) |
| Readiness probe | FAIL | FAIL: working_tree/current_main FAIL only because run was on a non-main SHA; runtime_provenance NOT_PROVEN |
| Overall | FAIL | FAIL (closed) |

Nightly Verify remains FAIL by design until the live sheet drift and runtime provenance are resolved with real evidence. PR #113 CI (encoding-safety x2, pytest) passed; merge awaits user approval.
## Addendum 2 - Secret Manager consumer trace (read-only, 2026-10-16 ~14:00 UTC)

OBSERVATION (gcloud, project fno-angel-prod-1790444589; secret values never read or printed):

- Cloud Run job `angel-market-scan-job` (asia-south1, runs as `angel-sheets-bot`) injects ANGEL_API_KEY, ANGEL_CLIENT_CODE, ANGEL_PIN, ANGEL_TOTP_SEED, plus SHEETS_KEY_JSON, SHEET_ID, BQ_PROJECT_ID from Secret Manager via secretKeyRef `@latest`. All 7 secrets grant `roles/secretmanager.secretAccessor` to `angel-sheets-bot` only.
- Triggered by Cloud Scheduler `angel-market-scan-mumbai` (15 9 * * 1-5) and `angel-market-scan-mumbai-preclose` (20 15 * * 1-5), both ENABLED. Executions 2026-10-16 03:45Z and 09:50Z completed successfully (failed executions seen on 2026-10-15 are not investigated here).
- Cloud Run service `angel-fno-scanner` (us-central1): no env vars and no secret references. Not a consumer.
- Repo code never calls the Secret Manager API (no access_secret_version). The only repo writer is `_migrate_secrets_one_time.yml` (adds versions from GitHub secrets).
- GitHub workflows (market_bot, phase2-angel-paper, phase3-angel-pnl, level3-pages) read GitHub Actions secrets, not Secret Manager. Two copies of the Angel credentials therefore exist: GitHub secrets (last updated 2026-09-26) and Secret Manager version 1 (2026-10-13).
- Project Data Access audit logging is not configured (no auditConfigs), so per-access history cannot be shown.

INFERENCE: production scanning depends on Secret Manager `@latest` being correct. Adding a version takes effect at the next job execution. Production does not use WIF, so missing WIF does not affect the running job.

Implications for the migrate run: a new version with wrong values would break the next scheduled scan; rollback is `gcloud secrets versions disable <n>` on the bad version. The migration identity needs only secretVersionAdder plus read access for `describe`, not Secret Manager Administrator.
## Addendum 3 - Investigation of 3 failed Cloud Run executions (2026-10-15) and related findings

OBSERVATION (Cloud Run job `angel-market-scan-job`, asia-south1; Cloud Logging REST; no secret values read):

| Execution | Start (UTC) | Started by | Image | Result | Error |
|---|---|---|---|---|---|
| kzvmb | 2026-10-15 09:50 | Cloud Scheduler (`angel-sheets-bot`), 15:20 IST pre-close | 8a2c642742 | FAIL exit 1 | `SchemaGuardError: live option_predictions_live is missing run_id; refusing WRITE_TRUNCATE` (guard from commit 2ed6839, 2026-10-14) |
| tvr28 | 2026-10-15 13:34 | manual, warghade2012@gmail.com | 8a2c642742 | FAIL exit 1 | `OPTION_PREDICTIONS readback differs from this cycle's intended output` (publication.py verify_outputs) |
| tcrvm | 2026-10-15 14:59 | manual, warghade2012@gmail.com | 562add4e8b | FAIL exit 1 | same readback mismatch |
| l7d96 | 2026-10-15 15:16 | manual, warghade2012@gmail.com | 2c42562256 | SUCCESS | - |
| bkzj8 | 2026-10-16 09:50 | Cloud Scheduler | 2c42562256 | SUCCESS | - |

- Both guards failed closed as designed: no partial publication was accepted (publication.py writes FAILED_PARTIAL).
- Failure 1 cause: live table lacked run_id at that moment. verify_all on 2026-10-16 shows run_id = STRING on all 4 tables (CLOSED by schema repair; the scheduled 15:20 IST Oct 15 cycle was lost and later replaced by a manual catch-up).
- Failures 2 and 3: cause of the readback mismatch is NOT PROVEN. Success followed only after a new image (2c42562256). No commit touching publication.py/sheet_grid.py exists on main after 2ed6839, so the fix is in code not on main, or in a non-publication file. Image-to-commit mapping is unavailable (no build labels/GIT_SHA env on the job).
- Manual runs used ALLOW_PRODUCTION_WRITES=1 and ANGEL_MARKET_SESSION=EOD, outside scheduled slots (19:04 IST and 20:29 IST), writing to production sinks.

COVERAGE GAP (OBSERVATION): the 09:15 IST run (execution spb2v) stops at MAX_RUNTIME_SECONDS=13800 and exited at 07:36:49Z (13:06 IST). The next scheduled run starts 15:20 IST. NSE trades until 15:30 IST, so live ingestion has no scheduled coverage for about 2h13m (13:07-15:20 IST). Job taskTimeout is 14400s. The scanner default is 22500s and `tests/test_runtime_safety.py` expects the schedule to cover the close. Per AGENTS.md section 12, data older than 180s during session is STALE.

DOC DRIFT (OBSERVATION): committed docs/migration-asia-south1 state the Mumbai job was not created and the US job remains. Live GCP shows only the asia-south1 job (created 2026-10-14) and asia-south1 schedulers ENABLED. The docs are stale.

STATUS: OBSERVED. Production changes (runtime cap, timeout, scheduler overlap, image provenance) are WAITING_FOR_USER approval.
## Addendum 4 - WIF provisioned and proven (owner-approved, 2026-10-16)

Authority: project owner (warghade2012@gmail.com, roles/owner verified) approved Package 1 and Package 3. PAPER_MODE=1, LIVE_ORDER_AUTHORITY=0. Production scanner untouched by Package 1.

Actions (all verified independently afterward):
- PR #113 merged as 6b036a4 (checks green: pytest, encoding-safety x2, Bugbot).
- Enabled sts.googleapis.com.
- Workload identity pool `github-actions`; OIDC provider `github-oidc`, attribute condition `assertion.repository=='psw2025-cmd/angel-fno-scanner'&&assertion.ref=='refs/heads/main'`.
- Service accounts: `angel-secret-migrator` (secretVersionAdder + viewer on the 4 Angel secrets only, serviceUsageViewer on project; impersonation allowed only from environment `gcp-secret-migration`); `angel-evidence-writer` (objectAdmin + legacyBucketReader on the evidence bucket only; impersonation from this repo).
- Bucket `gs://fno-angel-evidence`: asia-south1, uniform access, public access prevention enforced, versioning on.
- GitHub: variables GCP_WIF_PROVIDER, GCP_MIGRATION_SERVICE_ACCOUNT, GCP_EVIDENCE_SERVICE_ACCOUNT set; environment `gcp-secret-migration` limited to branch main.

Runs on main 6b036a4 (workflow_dispatch):

| Workflow | Run ID | Result |
|---|---|---|
| Migrate Secrets to GCP (one-time) | 38945257582 | PASS |
| NASA Daily Proof (read-only) | 38945241217 | PASS (cloud step) |

Evidence:
- Authentication: logs show the WIF provider and migration SA as inputs, "Created credentials file ... Successfully authenticated". The job passes no `credentials_json` and no static key. The credentials file is the short-lived external-account config, not a key.
- Secret Manager (direct gcloud): ANGEL_API_KEY, ANGEL_CLIENT_CODE, ANGEL_PIN, ANGEL_TOTP_SEED each have version 2 (created 2026-10-16 18:10:42-46 UTC), version 1 retained. Log shows SECRET_VERSION_ADDED for all four.
- Production safety: SHA-256 comparison (no values printed) shows version 2 IDENTICAL to version 1 for all four, so the live Cloud Run job (reads `latest`) is unaffected.
- NASA: log shows upload of PROVEN_PROOF_LEDGER.json and .sha256 to gs://fno-angel-evidence/nasa-daily-proof/38945241217/6b036a4a63c48a28a7e89c4aae2541217b00da9b/ and "GCS upload and readback verified". Independent check: downloaded object, recomputed SHA-256 d071d3ffd5a79a31e9d58da09a18aa9f41b39b42f8c6906e1e56ca2cc4bf94bd equals the recorded value (14595 bytes).

CAVEAT (OBSERVED): the NASA ledger content still reports PROOF_SUMMARY {"BLOCKED": 17, "FAIL": 1, "PASS": 7}. The workflow passes because its enforced gates are the cloud upload/readback and the CLI gate; the 17 BLOCKED and 1 FAIL checks are not enforced as failures. Investigation is OPEN.

Package 3: the Formula Checks contract in tools/verify_harness.py now uses the plain hyphen that the live sheet already has (ASCII, per PM-001); the formula is still compared exactly. Regression test: tests/test_formula_contract_ascii.py.
## Addendum 5 - Package 2 applied (live gap closed), 2026-10-16

OBSERVATION (before): job angel-market-scan-job generation 7, taskTimeout=14400, MAX_RUNTIME_SECONDS=13800 (3h50m); scheduler angel-market-scan-mumbai ENABLED 09:15 IST Mon-Fri, angel-market-scan-mumbai-preclose ENABLED 15:20 IST Mon-Fri. Scanner exits after MAX_RUNTIME_SECONDS, so the 09:15 run ended near 13:05 IST and the 15:20 run was the only cover for the close.

ACTION (owner approved "yes_now"):
- gcloud run jobs update angel-market-scan-job --region asia-south1 --task-timeout=25200 --update-env-vars=MAX_RUNTIME_SECONDS=24300
- gcloud scheduler jobs pause angel-market-scan-mumbai-preclose --location asia-south1 (paused, NOT deleted)

REASON: the BigQuery publication lease (paper-cycle:<date>:EOD, 900s) means a second execution while the first is still alive fails with PublicationLeaseError. Keeping the 15:20 job enabled alongside a full-day run would create a daily failed execution. One writer, one run, whole day.

OBSERVATION (after, independent describe): generation 8, taskTimeout=25200, maxRetries=0, MAX_RUNTIME_SECONDS=24300, same service account, same image digest, same env names, Ready=True. angel-market-scan-mumbai ENABLED 15 9 * * 1-5 Asia/Kolkata; angel-market-scan-mumbai-preclose PAUSED.

STATUS: IMPLEMENTED_NOT_DEPLOYED-to-proof. This is a config change, NOT a proven fix. Not RESOLVED_TWO_PARTY until the next trading day shows the 09:15 run alive until market close, no stale gap, lease and publication VERIFIED.

PASS CRITERIA for next trading day (Mon 2026-10-19 IST): one execution starts 09:15; still running at 15:00; ends at or just after 15:30 close (market-closed break) with success; no lease error; HEARTBEAT age <= 90s during session; no 15:20 execution.

ROLLBACK (exact):
- gcloud run jobs update angel-market-scan-job --region asia-south1 --task-timeout=14400 --update-env-vars=MAX_RUNTIME_SECONDS=13800
- gcloud scheduler jobs resume angel-market-scan-mumbai-preclose --location asia-south1

COST: Cloud Run job bills for run time (2 CPU / 4Gi). Run time rises from about 3h50m to about 6h15m per trading day (about 1.6x on the job compute). Exact figure to be measured from billing after the first full-day run.

KNOWN LIMITATIONS: a crash mid-day still leaves a gap until the next scheduled start because maxRetries=0 and the only other schedule is paused. Follow-up (Option B): idempotent watchdog trigger that exits 0 when the lease is held, so a crash is covered without failing executions. Weekday staleness alerting is also still missing.
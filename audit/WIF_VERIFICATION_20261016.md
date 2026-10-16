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
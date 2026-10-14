# Mumbai paper migration — gate matrix

Inspection time: 2026-10-14 05:25 IST onward. GCP project `fno-angel-prod-1790444589`. Repo `psw2025-cmd/angel-fno-scanner`.

Mumbai is not the live paper publisher. The US Cloud Run job `angel-market-scan-job` in `us-central1` is still present. Its scheduler is still present, was corrected from 03:45 IST to 09:15 IST, and was left **PAUSED**. No asia-south1 scheduler was created. No broker order method was called.

| Step | Result | Evidence |
| --- | --- | --- |
| 1. Preserve local work and cloud before-state | PASS | `evidence/20261014-052520/`. Local HEAD at inspection was `0e80b18b79f069df1c9813b1e210ef5472ee1a29` on `docs/trigger-reference`. Dirty tracked files `angel_prediction_engine.py` and `paper_log.py` were copied to `local-uncommitted.diff` and were not reverted. `move_agent_to_root` was rejected because this session is a subagent; files were written by absolute path. |
| 2. Prove and fix the scheduler clock | PASS | Before: cron `45 3 * * 1-5`, time zone `Asia/Kolkata`, which is 03:45 IST. Scheduler log severity ERROR at `2026-10-13T22:15:07Z` (03:45 IST on 14 Oct). An earlier ERROR at `2026-10-13T03:45:03Z` is 09:15 IST on 13 Oct. After: cron `15 9 * * 1-5`, time zone `Asia/Kolkata`, state `PAUSED`, `userUpdateTime` `2026-10-14T00:20:09Z`. Not resumed. Not deleted. |
| 3. Quote execution errors | PASS | `rc4bz` failed `ModuleNotFoundError: No module named 'tools.cycle_metadata'`. `2g9xq` failed `git rev-parse HEAD` exit 128. `t9j8j` completed successfully in 9m48.85s with no application traceback. |
| 4. Verify the deployed US image and sinks | PASS | Digest `sha256:c7a001cbaad51c9a815f49930a77f11f8652dbd0484b94e9062aa8b0ce89c59b`. Service account `angel-sheets-bot@fno-angel-prod-1790444589.iam.gserviceaccount.com`. Seven secrets: `ANGEL_API_KEY`, `ANGEL_CLIENT_CODE`, `ANGEL_PIN`, `ANGEL_TOTP_SEED`, `SHEETS_KEY_JSON`, `SHEET_ID`, `BQ_PROJECT_ID`. CPU 2, memory 4Gi, timeout 14400s, max retries 0. `RUN_ID=cloudrun-scheduled`, `GIT_SHA=cloudrun-image-v1`. Sheet `1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs`. BigQuery `fno-angel-prod-1790444589.fno_predictions.option_predictions_live` in `asia-south1`. |
| 5. Replace placeholder RUN_ID and GIT_SHA | PASS | `tools/cycle_provenance.py` rejects those placeholders. Cloud Run execution id and a 7-40 hex source commit are required. The US job env was not edited. |
| 6. One paper writer with a fence | PASS | `tools/publication_lease.py` uses a BigQuery transaction on `transaction_write_lock` and a monotonic token in `owner_id`. Live-order flags refuse the lease. Unit tests cover a second publisher being blocked and an expired writer being fenced. The lock table had 0 rows. The lease was not taken in production because paper writes stay off. |
| 7. Fix GH006 without weakening protection | BLOCKED | Run `38441552721` on `5f4c601a66926363f0a7ce24b94c95be969e39f7` failed with `remote: error: GH006: Protected branch update failed for refs/heads/main` after commit message `chore(data): auto-update daily prediction snapshots [skip ci]`. The workflow now pushes `data/snapshot-$GITHUB_RUN_ID` and opens a PR with no CI-skip marker. Merge of that code is not complete in this document revision. |
| 8. Restore GATE-06 and GATE-07 | PASS | Approved formulas are in committed `tools/verify_harness.py` (`d438502`). Restored and read back. `CE_PE_RANK!A5:A204` already had 200 nonempty cells. `C3:C218` had 216. Universe contract remains 219 (`GATE-01`, `EXPECTED_FNO_UNIVERSE_COUNT`). No paper trades were inserted. `data/paper_trades.csv` is header-only. |
| 9. Mumbai validation job, writes off | BLOCKED | Not created in this revision. The US job was not replaced. |
| 10. Validate the Mumbai job | BLOCKED | Depends on step 9. Market was closed during this inspection (before 09:15 IST), so an in-session freshness PASS was not available. |
| 11. Cut over the scheduler | BLOCKED | Step 10 is not PASS. The US scheduler was not deleted and was not resumed. No asia-south1 scheduler was created. |
| 12. Keep the US deployment | PASS | `angel-market-scan-job` and its scheduler still exist in `us-central1`. Asia-south1 Cloud Run job and service lists were empty at inspection. |

## Exact identities

- Local inspection HEAD: `0e80b18b79f069df1c9813b1e210ef5472ee1a29`
- `origin/main` at fetch: `5f4c601a66926363f0a7ce24b94c95be969e39f7`
- Deployed image tag: `us-central1-docker.pkg.dev/fno-angel-prod-1790444589/cloud-run-source-deploy/scanner:v1`
- Deployed image digest: `sha256:c7a001cbaad51c9a815f49930a77f11f8652dbd0484b94e9062aa8b0ce89c59b`
- Failed executions: `angel-market-scan-job-rc4bz`, `angel-market-scan-job-2g9xq`
- Successful execution: `angel-market-scan-job-t9j8j` (`2026-10-13T11:59:52.751309Z` to `2026-10-13T12:09:41.608646Z`)
- Scheduler after the correction: `15 9 * * 1-5` `Asia/Kolkata` `PAUSED`

## Sheet and BigQuery readback

- Dataset `fno_predictions` location `asia-south1`. There is no dataset named `option_data`.
- `option_predictions_live`: 219 rows.
- `option_predictions_live_backup_20261005`: 219 rows. Not deleted.
- `transaction_write_lock`: 0 rows.
- Formula Checks `C10` read back `=COUNTA(CE_PE_RANK!A5:A204)&" / 200"`.
- Formula Checks `E10` read back `=IF(COUNTA(CE_PE_RANK!A5:A204)=200,"PASS","FAIL")`.
- Formula Checks `C11` read back `=COUNTIF(CE_PE_RANK!U5:U204,"HIGH MOMENTUM")`.
- Sheet revision ids were not retrieved. `gcloud` was not on PATH for the virtualenv Python process (`WinError 2`). No cell dump was exported.

## Cost

BLOCKED. Billing is enabled for `billingAccounts/012A4D-4C52EF-195922`. The project has no BigQuery billing-export dataset (the only dataset is `fno_predictions`), so there is no measured SKU cost. This is not a claim of zero cost. Observed compute shape of the US job is 2 vCPU and 4 GiB. `t9j8j` ran for about 589 seconds.

## IAM

`user:warghade2012@gmail.com` is `roles/owner`. No binding for `roles/bigquery.admin` was present. None was granted.

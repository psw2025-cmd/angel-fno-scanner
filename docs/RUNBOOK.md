# Runbook

Standard Operating Procedures (SOPs) for operating, testing, migrating, and recovering the Angel F&O Scanner system.

---

## 1. How to Verify the System
Run the unified verification command from the repository root:
```powershell
python tools/verify_all.py
```
This executes:
- Git status check (clean working tree)
- Git synchronization check (aligned with `origin/main`)
- Pytest regression suite (`154 passed`)
- BigQuery `run_id` type verification across all four tables (must be `STRING`)
- Infrastructure readiness probe (verifies 12 gates)
- Saves JSON summary to `audit/verify_report.json`

---

## 2. How to Check BigQuery `run_id` Types
Execute the standalone type checker:
```powershell
python tools/check1_runid_types.py
```
Expected output:
```text
Table: option_predictions_live         | Column: run_id | Type: STRING [OK]
Table: market_news_sentiment           | Column: run_id | Type: STRING [OK]
Table: next_day_gap_predictions        | Column: run_id | Type: STRING [OK]
Table: prediction_calibration_log      | Column: run_id | Type: STRING [OK]
```

---

## 3. How to Run the Readiness Probe
Run the standalone readiness probe PowerShell script:
```powershell
powershell.exe -ExecutionPolicy Bypass -NoProfile -File .\scripts\prepare_infra_readiness.ps1 -VerifyOnly -OutputRoot C:\Temp\verify
```
Summary target:
- 10 gates `PASS`
- 1 gate `NOT_PROVEN` (`runtime_provenance` — clears after live market_bot execution)
- 1 gate `UNKNOWN` (`exact_sha_ci` — clears when PR Tests runs on HEAD)
- 0 gates `FAIL`

---

## 4. How to Migrate a BigQuery Schema Change
1. Capture pre-change snapshot:
   ```powershell
   python tools/snapshot_state.py
   ```
2. Write the DDL statements into a versioned migration file (e.g. `tools/migrate_xxx.sql`).
3. Wrap in a reversible script that creates a backup table `<table>_backup_<YYYYMMDD_HHMMSS>`, executes the DDL, and queries `INFORMATION_SCHEMA.COLUMNS` to verify.
4. Document the migration and rollback SQL in `docs/CHANGELOG.md`.
5. Run full verification:
   ```powershell
   python tools/verify_all.py
   ```

---

## 5. How to Roll Back a Schema Change
If a schema change causes failures:
1. Restore from the backup table created in Step 4:
   ```sql
   CREATE OR REPLACE TABLE `fno-angel-prod-1790444589.fno_predictions.<table>`
   PARTITION BY <partition_spec>
   CLUSTER BY <cluster_spec>
   AS SELECT * FROM `fno-angel-prod-1790444589.fno_predictions.<table>_backup_<timestamp>`;
   ```
2. Revert the code change:
   ```powershell
   git revert <commit-sha>
   git push origin main
   ```
3. Run `python tools/verify_all.py` to confirm recovery.

---

## 6. How to Recover from a Partial Code Fix
If an agent's code modification breaks tests or corrupts files:
1. Revert the uncommitted file immediately:
   ```powershell
   git checkout HEAD -- <affected_file>
   ```
2. Confirm the test suite returns to passing:
   ```powershell
   .\.venv\Scripts\pytest.exe -q
   ```
3. Never stack additional partial fixes on top of broken code. Diagnose the root cause first.

---

## 7. How to Open a New Defect
1. Add an entry to `docs/DEFECT_REGISTER.md` with status `OPEN`.
2. Create `docs/decisions/D-XX.md` documenting description, evidence, impact, options, and recommended action.
3. Commit and push:
   ```powershell
   git add docs/DEFECT_REGISTER.md docs/decisions/D-XX.md
   git commit -m "docs(defect): register D-XX <short description>"
   git push origin main
   ```

---

## 8. How to Close a Defect
1. Implement the fix with accompanying regression test.
2. Run `python tools/verify_all.py` to ensure zero regressions.
3. Update `docs/DEFECT_REGISTER.md` setting status to `CLOSED` and record the commit SHA.
4. Add a section to `docs/CHANGELOG.md` with What, Why, Evidence, and Rollback.
5. Update `docs/AGENT_HANDOFF.md`.
6. Commit and push together.

---

## 9. Nightly Verification Failures
When the GitHub Actions `Nightly Verify` workflow fails:
1. Read the workflow run failure logs and download `audit/verify_report.json`.
2. Run `python tools/verify_all.py` locally on the workstation to reproduce the failure.
3. If confirmed, register a new defect row in `docs/DEFECT_REGISTER.md` and create `docs/decisions/D-XX.md`.
4. Follow the standard fix, test, verify, and close lifecycle.

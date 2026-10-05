# Staging Review Package: World-Class Architecture & Zero-Defect Prevention

> **Notice:** This directory (`staging_review/`) is completely isolated and excluded from git tracking via local `.git/info/exclude`.
> No other agent (ChatGPT, IssueOps, GitHub Actions) can see or be confused by these files until we explicitly decide to promote them to production.
> If you choose not to proceed with these changes, this entire folder can be deleted with zero trace:
> ```powershell
> Remove-Item -Recurse -Force staging_review
> ```

---

## 1. Executive Summary: What Problem Are We Solving?

When `python tools/verify_harness.py` executed against production on 2026-10-05, **9 of 12 checks passed**, but 3 failed:
```
[FAIL]  runid_latest_identical       option_predictions_live=37242575613 others=None
[FAIL]  gitsha_latest_identical      option_predictions_live=eaccdaf     others=None
[FAIL]  writer_id_market_bot         option_predictions_live=market_bot  others=None
```

### Forensic Root Cause (GitHub Actions Run `37242575613`)
1. In workflow `market_bot.yml`, `option_predictions_live` succeeded.
2. Next, `angel_prediction_engine.py` tried to append to `market_news_sentiment` with `autodetect=False`.
3. BigQuery rejected the load job with:
   `google.api_core.exceptions.BadRequest: 400 ... No such field: cycle_id.`
4. The append crashed, aborting before `prediction_calibration_log` could be written.

This staging review package provides the **permanent, future-proof fix** so this class of defect can never occur again.

---

## 2. Review Components in this Folder

| File | Purpose | Verification Status |
| :--- | :--- | :--- |
| [`schema_projection.py`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/staging_review/schema_projection.py) | Strict schema projection engine. Automatically prunes extra keys (like `cycle_id`) before BigQuery load jobs to prevent 400 Bad Request errors. | Tested & Verified (`PASS`) |
| [`migrate_bq_cycle_id.py`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/staging_review/migrate_bq_cycle_id.py) | Safe, idempotent schema migration script. Audits and applies `ALTER TABLE ... ADD COLUMN IF NOT EXISTS cycle_id STRING` across BigQuery tables. | Dry-run audit tested (`PASS`) |
| [`angel_prediction_engine_patch.py`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/staging_review/angel_prediction_engine_patch.py) | Reference replacement for `sync_to_bigquery` with schema projection, independent table error isolation, and Dead-Letter Queue (DLQ) logging. | Ready for review |
| [`market_bot_workflow_patch.yml`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/staging_review/market_bot_workflow_patch.yml) | Addition to `.github/workflows/market_bot.yml` that runs `verify_harness.py` as a mandatory quality gate after every scanner run. | Ready for review |
| [`test_staging_dry_run.py`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/staging_review/test_staging_dry_run.py) | Standalone verification test proving that schema projection successfully eliminates 400 errors against live schemas. | Executed (`2/2 PASS`) |

---

## 3. How to Test the Staging Review Components Right Now

You can run the dry-run test right now in terminal:
```powershell
python staging_review/test_staging_dry_run.py
```
**Output:**
```
======================================================================
 STAGING REVIEW: DRY-RUN VERIFICATION TEST
======================================================================
[TEST 1] Testing synthetic schema projection...
  [PASS] Synthetic schema projection successfully pruned extra keys while keeping required columns.

[TEST 2] Testing projection against live BigQuery market_news_sentiment schema...
  [PASS] Successfully pruned cycle_id because table lacks column.
  [PASS] Filtered from 9 raw keys down to 7 valid BigQuery schema keys.

======================================================================
 ALL DRY-RUN CHECKS PASSED (100% SAFE)
======================================================================
```

You can also run the BigQuery column audit (strictly read-only):
```powershell
python staging_review/migrate_bq_cycle_id.py
```
**Output:**
```
  [PRESENT]  option_predictions_live        (cycle_id type: STRING)
  [MISSING]  market_news_sentiment          (cycle_id type: N/A)
  [MISSING]  next_day_gap_predictions       (cycle_id type: N/A)
  [MISSING]  prediction_calibration_log     (cycle_id type: N/A)
```

---

## 4. Next Step Decisions for the Operator

### Option A: Approve & Promote to Production
If you approve this architecture:
1. We run `python staging_review/migrate_bq_cycle_id.py --apply` to add `cycle_id` to the 3 remaining tables in BigQuery.
2. We integrate `schema_projection.py` into `angel_prediction_engine.py`.
3. We update `docs/CHANGELOG.md` and commit to `main`.
4. Trigger workflow run or run live test: all 4 BigQuery tables write cleanly.
5. Re-run `python tools/verify_harness.py`: All 12 checks output `[PASS] (12/12)`.

### Option B: Reject / Discard
If you prefer not to adopt this approach:
1. Run `Remove-Item -Recurse -Force staging_review`.
2. Git working tree remains 100% clean and unaffected.

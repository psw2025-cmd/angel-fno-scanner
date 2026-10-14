# option_predictions_live schema repair

Base commit: `44c5b934144fdbb477c31ff1b42fa84db5dfcf98` (merged PR #95). PR #46 was not used.

Mumbai image deploy was not resumed. No Mumbai Cloud Run job or scheduler was created. The US scheduler `angel-market-scan-job` was not resumed. The GitHub Market Bot was not re-enabled. No broker order was placed.

## Status

| Item | Status | Evidence |
| --- | --- | --- |
| 1. Name the writer | VERIFIED | Load job `9c6994fa-c401-4b98-ac08-0c4a0518c256` |
| 2. Fail closed on a bad committed schema | TESTED | `tests/test_live_schema_guard.py` |
| 3. Refuse WRITE_TRUNCATE when the live table is incomplete | TESTED | same tests; call in `sync_to_bigquery()` |
| 4. Stale narrower schema cannot replace the table through this path | TESTED | guard refuses autodetect and a narrower load. Not deployed to the existing US image |
| 5. Preserve 219 rows and capture before-state | VERIFIED | `before-identity.json`, backup table |
| 6. Additive column repair only | VERIFIED | `ALTER TABLE ... ADD COLUMN`; identity hash unchanged |
| 7. Regression tests | TESTED | 7 passed |
| 8. Independent readback | VERIFIED | five fields, correct types, 219 rows |

## Writer

The schema now on the table was produced by BigQuery load job `9c6994fa-c401-4b98-ac08-0c4a0518c256` in `asia-south1`.

- creation recorded by the audit log at `2026-10-13T20:07:13Z`
- principal `angel-sheets-bot@fno-angel-prod-1790444589.iam.gserviceaccount.com`
- caller IP `34.142.183.140`
- client `gl-python/3.12.3 grpc/1.83.0 gax/2.34.0 gapic/3.43.0 gccl/3.43.0`
- `jobType=LOAD`, `writeDisposition=WRITE_TRUNCATE`, `autodetect=true`
- load schema field count 0, `run_id` absent
- `outputRows=219`
- destination `fno_predictions.option_predictions_live`

That job is not Cloud Run execution `angel-market-scan-job-t9j8j`. The execution's load job `a5ecf942-c5c6-4a31-884b-aea9bcc4861c` at `2026-10-13T12:08:43Z` had `autodetect=false`, its job document contains `run_id`, and its audit caller IP was `2600:1900:0:2d0b::1600`. Cloud Run job and service logs for `2026-10-13T20:06:00Z` through `2026-10-13T20:10:00Z` are empty.

It is not a GitHub Actions run. The market-bot run `38441552721` completed at `2026-10-13T17:56:07Z`. Nightly Verify run `38470161057` started at `2026-10-13T21:22:56Z`.

This project's Cloud Run inventory is the US service `angel-fno-scanner` and the US job `angel-market-scan-job`. Cloud Functions and Compute Engine APIs are disabled, so those inventories were not available. No resource in this project is named as the process behind `34.142.183.140`. The named writer is the autodetect load job and service account above.

Current `sync_to_bigquery()` on `44c5b93` uses `load_schema("option_predictions_live")` with `autodetect=False`. That path did not issue the 20:07 job. Commit `eaccdaf2e7874c77061fec007980b1c1d13c23c1` (2026-10-05) pinned `autodetect=False`. The 20:07 client is an older or alternate Python writer that still loads with autodetect.

## Schema

Before: 48 fields. Provenance fields absent. `snapshot_timestamp` was present as TIMESTAMP. Row count 219. Distinct symbols 219. Identity hash `1d69db32fc279b74da1f0e1069aa3bf37f905cc199ed14da08a969c4d47d17ce`.

Backup copy, not a delete: `fno_predictions.option_predictions_live_backup_20261014_schema_repair` has 219 rows. `option_predictions_live` and `option_predictions_live_backup_20261005` were not deleted. The 20261005 INTEGER `run_id` schema was not restored.

Repair: `ALTER TABLE` added nullable `cycle_id STRING`, `source_timestamp TIMESTAMP`, `writer_id STRING`, `git_sha STRING`, and `run_id STRING`. These match `schemas/option_predictions_live.json`. No historical values were written.

After: 53 fields. Added only those five. Dropped none. Retyped none. Information schema: all five nullable; `run_id` STRING; `source_timestamp` TIMESTAMP. Row count 219. The identity hash is unchanged. All 219 provenance values are null.

## Tests

```
pytest tests/test_live_schema_guard.py -q
7 passed in 0.64s
```

The tests refuse a committed schema missing `run_id`, an INTEGER `run_id`, a live table missing provenance, an autodetect truncate, and a load schema that drops a live column.

## Sheet

`FORENSIC_LIVE!B2:B220` and `option_predictions_live.symbol` are the same 219 symbols. `only_in_sheet=0`, `only_in_bq=0`.

## Not activated

US scheduler remained PAUSED at `15 9 * * 1-5` `Asia/Kolkata` on the read during this repair. No asia-south1 scheduler was listed. Mumbai publishing was not started. The US job image was not replaced.

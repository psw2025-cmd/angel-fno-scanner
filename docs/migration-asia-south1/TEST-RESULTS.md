# Test results

Command:

`python -m pytest -q tests/test_cycle_provenance_and_lease.py tests/test_snapshot_push_failure.py tests/test_single_writer_architecture.py tests/test_universe_contract.py tests/test_publication_integrity.py`

Result: 44 passed.

Covered:

- placeholder `cloudrun-scheduled` is replaced by `CLOUD_RUN_EXECUTION`
- placeholder `cloudrun-image-v1` is rejected
- a second paper publisher is blocked while the lease is live
- an expired lease fences the stale writer with a new token
- live-order flag `ALLOW_LIVE_BROKER_ORDERS=1` refuses the lease
- snapshot workflow no longer pushes `HEAD:main` and no longer contains a CI-skip marker

Not covered by this run: a live Mumbai Cloud Run execution, an in-session exchange-tick freshness pass, or a production lease row. The lock table count remained 0.

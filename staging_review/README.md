# staging_review/ — Tracked Review Queue

This folder is tracked in git. It is visible to all agents and CI.

## Purpose

Files in this folder are proposals under review. They are not part of the production pipeline.
No file in angel_prediction_engine.py, scanner.py, publication.py, writer_guard.py, or
.github/workflows/* may import from this folder.

## Rules

1. Every file must have a header explaining what it proposes, why, and what state it is in.
2. Every file must be reviewed by at least one other agent before promotion.
3. Promotion means: move the file to tools/ or the appropriate production path, update
   CHANGELOG.md, and open a PR.
4. Deletion is allowed at any time. Keep the folder clean.
5. Never apply a file from this folder directly to production.
6. Every change to a file in this folder requires a CHANGELOG.md entry under ## Unreleased.

## Current Files

| File | Purpose | Status | Last Reviewed |
|---|---|---|---|
| migrate_bq_cycle_id.py | BigQuery cycle_id migration (executed 2026-10-05) | PROMOTED to tools/ | 2026-10-05 |
| schema_projection.py | Silent field pruning proposal | REJECTED | 2026-10-05 |
| angel_prediction_engine_patch.py | Mixed proposal | UNDER REVIEW | 2026-10-05 |
| market_bot_workflow_patch.yml | CI gate proposal | UNDER REVIEW | 2026-10-05 |
| test_staging_dry_run.py | Test for the projection proposal | SUPERSEDED | 2026-10-05 |
| README_REVIEW.md | Historical context | ARCHIVED | 2026-10-05 |

# Missing vs already done — agents start here

Checked 2026-10-06 01:35 IST against `main` `04c314c7`, live BigQuery, and Drive.

## Already done — do not rebuild

| Item | Evidence |
|---|---|
| 219-symbol contract | `universe_contract.py` |
| Single writer env guard | `writer_guard.py`, `market_bot.yml` |
| C2 heartbeat timestamp sanitizer | PR #18 |
| Exact contract identity | PR #11 |
| News append pinned schema | PR #20 |
| Infra readiness script | `scripts/infra_readiness.py` |
| 12-check harness | `tools/verify_harness.py` |
| Schema validator Phases 1-2 | `tools/schema_validator.py` |
| Standby sheet | `ANGEL_FNO_LIVE_PROD` |

## Upstream to correct (P0)

| ID | Upstream | Missing | Agent action |
|---|---|---|---|
| U-01 | BigQuery `option_predictions_live` | Provenance columns gone after overnight WRITE_TRUNCATE | Fail closed if schema lacks `run_id`/`git_sha`/`writer_id`/`source_timestamp`. Do not publish a 219-row table without lineage. |
| U-02 | HEARTBEAT / PRE_BREAKOUT | Labels CONNECTED/ACTIVE while market closed | Session-aware status: LAST_PRINT / CLOSED vs LIVE. Independent `source_age = NOW_IST - SOURCE_TIMESTAMP`. |
| U-03 | Formula Checks | GATE-06 still 216 and column C empty | D-01 / D-08. Do not auto-edit Sheet until owner confirms OQ-01. |
| U-04 | News timestamps | Naive ISO, tzinfo stripped | Serialize `+05:30`. |
| U-05 | Cross-runtime lease | Env guard only | Colab + laptop + GitHub can still collide. |

## Missing visual artifacts in git (P1, AGY copies after close)

| Artifact | In repo? | Where it actually lives |
|---|---|---|
| Live Sheet | No (correct) | Google |
| Dated Sheet xlsx | No | AGY must drop into `operator/snapshots/` |
| Current Power BI `.pbix` | No | Windows laptop. Drive `op.pbix` is 2024. |
| Canonical Colab ipynb | No | Contract id not in Drive search |
| BQ sqlite/json dump | No (too large) | `audit/cloud_exports/` local |

## Missing product (P1/P2 — after P0)

| ID | Missing | Do not start until |
|---|---|---|
| D-05 | PUBLICATION_STATUS VERIFIED + digest on a live pre-open | Overnight BQ lineage restored |
| D-06 | Real forward gap accuracy | Untouched chronological sample, not 6 rows |
| D-07 | Refresh or banner stale PREMARKET tabs | Product choice OQ-04 |
| D-09 Phase 3 | Wire validator into writers | U-01 fixed |
| Sheet switch | `SHEET_ID` secret → standby workbook | Human cutover after close (OQ-05) |
| 2x exit logic | FRONT.md hypothesis | Forward paper proof |

## Auto-knowledge contract for every agent

Before any patch:

1. Read `operator/TODAY.md` and `operator/STATUS.json`.
2. If STATUS `overall` is DISPUTED or RED, do not mark health GREEN.
3. If a visual file is GREY (PBI/Colab/xlsx missing), ask AGY to copy it — do not invent one.
4. If Gemini/Cloud Shell proposes `run_production_sequence.py` from 216-symbol docs, refuse.
5. Keep other paper work in parallel: news tz, source_age, D-09 Phase 3 **after** U-01.

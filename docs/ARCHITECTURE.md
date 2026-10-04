# Architecture

## Overview
The **Angel One NSE F&O Scanner and Market Intelligence System** is an evidence-driven, paper/analyzer platform that ingests real-time exchange quotes across a verified 219-symbol derivatives universe, calculates Black-76 option Greeks, evaluates multi-factor Bayesian directional conviction, and publishes synchronized, tamper-evident snapshots to Google Sheets and Google BigQuery. The system operates strictly in PAPER/ANALYZER mode with zero live-order placement authority, enforces single-writer exclusivity via environment leases, and guarantees end-to-end data provenance across all data sinks.

## Data Flow
```text
Angel One SmartAPI (FULL quotes: LTP, OI, Volume, Prev Close)
       │
       ▼
 [scanner.py] ── Main loop & orchestrator
       │
       ├─► [gainers.py] ── Computes Black-76 Greeks & ranks top 200 liquid CE/PE gainers
       │
       ├─► [angel_prediction_engine.py] ── Next-day gap models, sentiment, weights
       │
       ▼
 [publication.py] & [writer_guard.py] ── Single-writer lease & digest validation
       │
       ├─────────────────────────────────┬────────────────────────────────┐
       ▼                                 ▼                                ▼
 Google Sheets (17 tabs)           Google BigQuery (5 tables)       Local JSON/Audit
 - FORENSIC_LIVE                   - option_predictions_live         - data/summary.md
 - OPTION_PREDICTIONS              - market_news_sentiment          - data/*.json
 - CE_PE_RANK                      - next_day_gap_predictions       - audit/snapshots/
 - HEARTBEAT                       - prediction_calibration_log
 - PUBLICATION_STATUS
```

## Components

### 1. `scanner.py`
- **Purpose**: Main process entrypoint and continuous quote scanning loop. Orchestrates batch quote fetching, option chain assembly, gainer calculations, and invocation of prediction sync.
- **Public functions**: `main()`, `run_scan_cycle()`, `fetch_fno_quotes()`, `write_grid()`, `update_heartbeat()`.
- **Dependencies**: `smartapi-python`, `gspread`, `gainers.py`, `angel_prediction_engine.py`, `universe_contract.py`, `writer_guard.py`.
- **Sinks**: Writes to Google Sheet tabs (`FORENSIC_LIVE`, `HEARTBEAT`, `OPTION_PREDICTIONS`, `TOP_GAINERS`, `CE_PE_RANK`, `NEWS_LIVE`), local `data/` snapshots.

### 2. `angel_prediction_engine.py`
- **Purpose**: Predictive intelligence engine. Models next-day opening gap magnitude/direction (Target A), ranks exact CE/PE option contracts for explosive moves (Targets B & C), executes Bayesian online weight calibration, and writes to BigQuery.
- **Public functions**: `sync_to_bigquery()`, `journal_pre_close_paper_trades()`, `reconcile_next_day_gap_trades()`, `build_news_append_job_config()`, `is_market_open()`, `is_pre_close_time()`.
- **Dependencies**: `google-cloud-bigquery`, `gspread`, `market_calendar.py`, `writer_guard.py`, `universe_contract.py`.
- **Sinks**: BigQuery tables (`option_predictions_live`, `market_news_sentiment`, `next_day_gap_predictions`, `prediction_calibration_log`), Google Sheet tabs (`PAPER_ALERT_LOG`, `OPTION_PREDICTIONS`).

### 3. `publication.py`
- **Purpose**: Publication integrity manager. Generates SHA-256 matrix digests of sheet grids and validates readback consistency across Google Sheets and BigQuery before marking a publication cycle successful.
- **Public functions**: `verify_outputs()`, `verify_current_publication()`, `matrix_hash()`, `status_worksheet()`.
- **Dependencies**: `hashlib`, `gspread`, `sheet_grid.py`, `writer_guard.py`, `universe_contract.py`.
- **Sinks**: Google Sheet tab (`PUBLICATION_STATUS`).

### 4. `writer_guard.py`
- **Purpose**: Single-writer enforcement and provenance attestation. Blocks unauthorized write operations outside `market_bot` and injects execution lineage into every outgoing payload.
- **Public functions**: `require_authorized_writer()`, `build_provenance()`, `append_sheet_provenance()`.
- **Dependencies**: `os`, `datetime`, `zoneinfo`, `contextvars`.
- **Sinks**: Google Sheet tab (`WRITE_PROVENANCE`).

### 5. `universe_contract.py`
- **Purpose**: Universe integrity gate. Freezes the F&O universe to exactly 219 canonical symbols listed in `agent_manifest.json`. Fails closed if any symbol is missing or unexpected.
- **Public functions**: `verified_symbols()`, `select_verified_universe()`, `require_verified_symbols()`.
- **Dependencies**: `json`, `pathlib`.
- **Sinks**: None (pure validation guard).

### 6. `gainers.py`
- **Purpose**: Real-time rank and Greeks layer. Computes Black-76 implied volatility, delta, and theta per day, applies liquidity gates, and caps top gainers at 200 contracts.
- **Public functions**: `build_gainers()`, `black_76_call()`, `black_76_put()`, `implied_volatility()`, `market_is_open()`.
- **Dependencies**: `math`, `dataclasses`, `datetime`, `market_calendar.py`.
- **Sinks**: In-memory rank tables passed to `scanner.py` for sheet publication.

### 7. `credentials.py`
- **Purpose**: Unified credentials and environment resolver. Discovers service account keys, `.env` files, and GitHub Actions secret mappings with zero hardcoded credentials.
- **Public functions**: `load_env()`, `resolve_service_account_path()`, `get_credentials()`.
- **Dependencies**: `json`, `os`, `pathlib`.
- **Sinks**: None (environment configuration).

---

## Contracts

1. **Universe Contract**: Exactly 219 F&O symbols, verified and frozen in `agent_manifest.json`. No partial write (<219) may overwrite a live production snapshot.
2. **Single-Writer Contract**: Only `WRITER_ID=market_bot` with `ALLOW_PRODUCTION_WRITES=1` is authorized to publish. Manual, dispatch, and test workflows fail closed.
3. **Provenance Contract**: Every record written to BigQuery or Google Sheets MUST include four core lineage fields:
   - `run_id`: STRING (GitHub Action Run ID or explicit run identifier)
   - `git_sha`: STRING (exact 40-char commit SHA)
   - `writer_id`: STRING (`market_bot`)
   - `source_timestamp`: STRING / TIMESTAMP (timezone-aware IST timestamp)
4. **Data Type Uniformity**: All provenance fields are persisted as `STRING` in all sinks to prevent autodetect numeric coercion bugs.

---

## Sinks

### Google Sheet Tabs (`1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs`)
1. `HEARTBEAT` — System heartbeat, writer age, cycle counters, BQ sync status.
2. `FORENSIC_LIVE` — 219 rows × 18 columns full-universe market snapshot.
3. `OPTION_PREDICTIONS` — Master prediction table with Greeks and directional ratings.
4. `CE_PE_RANK` — Top 200 liquid option contracts ranked by gain.
5. `TOP_GAINERS` — Secondary gainer board.
6. `NEWS_LIVE` — Scraped financial news headlines and sentiment scores.
7. `PUBLICATION_STATUS` — SHA-256 digest verification and publication state.
8. `WRITE_PROVENANCE` — Audit log of all sink writes.
9. `PAPER_ALERT_LOG` — Paper trade execution log for pre-close gap picks.
10. `Formula Checks` — Consumer validation gate surface.

### BigQuery Tables (`fno-angel-prod-1790444589.fno_predictions`)
1. `option_predictions_live` — WRITE_TRUNCATE latest deduplicated live snapshot (219 rows). Partitioned by `DATE(snapshot_timestamp)`, clustered by `symbol`, `directional_bias`.
2. `market_news_sentiment` — WRITE_APPEND deduplicated news headlines and Bayesian tone scores.
3. `next_day_gap_predictions` — WRITE_APPEND overnight pre-close gap predictions and reconciliation outcomes.
4. `prediction_calibration_log` — WRITE_APPEND online multi-factor model weight adjustments and hit rates.

---

## Failure Modes & Mitigations

1. **Partial Universe Delivery**: If quote fetch discovers <219 symbols, `universe_contract.py` raises `RuntimeError`. The pipeline halts and preserves the last-known-good snapshot.
2. **BigQuery Type Coercion**: BigQuery autodetect coercing `run_id` to INT64 is prevented by pinning table schema (`schema=table.schema`) and setting `autodetect=False` across all five load job configs.
3. **Out-of-Order Multi-Tab Writes**: If BigQuery fails after Google Sheets updates, `publication.py` records `FAILED_PARTIAL` in `PUBLICATION_STATUS`. Consumers calling `verify_current_publication()` reject the partial state.
4. **Exchange Calendar Anomalies**: `market_calendar.py` uses the official 2026 NSE holiday schedule. Unknown years or unreviewed dates fail closed.
5. **Concurrent Run Collisions**: GitHub Actions `market_bot.yml` enforces concurrency groups (`cancel-in-progress: false`), and `writer_guard.py` verifies runtime credentials before opening writes.

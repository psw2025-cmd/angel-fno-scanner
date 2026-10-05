# Data Contracts

These are the required schemas for every BigQuery table in `fno-angel-prod-1790444589.fno_predictions`. Any change to any column type requires:
1. A backup table (e.g. `<table>_backup_<YYYYMMDD_HHMMSS>`)
2. A migration via `tools/migrate_schema.py`
3. A `CHANGELOG.md` entry documenting what, why, evidence, and rollback SQL
4. A schema verification query after the change

Provenance fields (`run_id`, `git_sha`, `writer_id`, `source_timestamp`) MUST be:
- `run_id`: STRING (never INT64)
- `git_sha`: STRING
- `writer_id`: STRING
- `source_timestamp`: TIMESTAMP / STRING (timezone-aware)

Breaking this contract causes the readiness probe to FAIL.

---

## 1. `option_predictions_live`
- **Table ID**: `fno-angel-prod-1790444589.fno_predictions.option_predictions_live`
- **Rows**: 219 (authoritative latest snapshot)
- **Time Partitioning**: `DAY` on `snapshot_timestamp`
- **Clustering Fields**: `['symbol', 'directional_bias']`
- **Write Disposition**: `WRITE_TRUNCATE`

| Column Name | Type | Mode | Description |
|---|---|---|---|
| `symbol` | STRING | NULLABLE | Underlying NSE F&O Symbol (e.g. `NIFTY`, `RELIANCE`) |
| `rank` | INTEGER | NULLABLE | Intraday conviction rank (1 to 219) |
| `directional_bias` | STRING | NULLABLE | Directional stance (`CALL`, `PUT`, `NEUTRAL`) |
| `spot_ltp` | FLOAT | NULLABLE | Last traded price of underlying |
| `atm_strike` | FLOAT | NULLABLE | At-the-money strike price |
| `expiry` | DATE | NULLABLE | Option contract expiry date (`YYYY-MM-DD`) |
| `confidence_pct` | FLOAT | NULLABLE | Model confidence score (0.0 to 100.0) |
| `ce_win_prob` | FLOAT | NULLABLE | Calibrated probability of CE extreme gain |
| `pe_win_prob` | FLOAT | NULLABLE | Calibrated probability of PE extreme gain |
| `action_rating` | STRING | NULLABLE | Actionable rating label |
| `intensity_score` | INTEGER | NULLABLE | Momentum intensity rating |
| `atm_pcr` | FLOAT | NULLABLE | Put-Call Ratio at ATM strike |
| `max_pain` | FLOAT | NULLABLE | Max pain strike level |
| `ce_ltp` | FLOAT | NULLABLE | Call option LTP |
| `ce_chg_pct` | FLOAT | NULLABLE | Call option % change |
| `ce_oi` | INTEGER | NULLABLE | Call open interest |
| `ce_oi_change_pct` | FLOAT | NULLABLE | Call OI velocity % |
| `ce_iv` | FLOAT | NULLABLE | Call Black-76 implied volatility |
| `ce_delta` | FLOAT | NULLABLE | Call Black-76 delta |
| `ce_gamma` | FLOAT | NULLABLE | Call Black-76 gamma |
| `ce_theta` | FLOAT | NULLABLE | Call Black-76 theta per day |
| `ce_vega` | FLOAT | NULLABLE | Call Black-76 vega |
| `ce_bid_ask_spread` | FLOAT | NULLABLE | Call spread ratio |
| `pe_ltp` | FLOAT | NULLABLE | Put option LTP |
| `pe_chg_pct` | FLOAT | NULLABLE | Put option % change |
| `pe_oi` | INTEGER | NULLABLE | Put open interest |
| `pe_oi_change_pct` | FLOAT | NULLABLE | Put OI velocity % |
| `pe_iv` | FLOAT | NULLABLE | Put Black-76 implied volatility |
| `pe_delta` | FLOAT | NULLABLE | Put Black-76 delta |
| `pe_gamma` | FLOAT | NULLABLE | Put Black-76 gamma |
| `pe_theta` | FLOAT | NULLABLE | Put Black-76 theta per day |
| `pe_vega` | FLOAT | NULLABLE | Put Black-76 vega |
| `pe_bid_ask_spread` | FLOAT | NULLABLE | Put spread ratio |
| `news_sentiment_score` | FLOAT | NULLABLE | Bayesian news sentiment score (-1.0 to +1.0) |
| `news_impact_rating` | STRING | NULLABLE | Sentiment classification |
| `top_news_headline` | STRING | NULLABLE | Most influential headline snippet |
| `news_source_tier` | STRING | NULLABLE | Media tier classification |
| `news_severity_level` | INTEGER | NULLABLE | Impact severity level |
| `positive_prob` | FLOAT | NULLABLE | News probability positive |
| `negative_prob` | FLOAT | NULLABLE | News probability negative |
| `already_priced_in_prob` | FLOAT | NULLABLE | News priced-in factor |
| `market_confirmation` | STRING | NULLABLE | Order-flow confirmation flag |
| `expected_gap_pct` | FLOAT | NULLABLE | Next-day opening gap magnitude % |
| `gap_direction` | STRING | NULLABLE | Next-day opening gap direction |
| `pre_open_conviction_pct` | FLOAT | NULLABLE | Pre-open gap conviction score |
| `target_open_strike` | STRING | NULLABLE | Recommended target option strike |
| `expected_move_band` | STRING | NULLABLE | Expected move range |
| `data_freshness_status` | STRING | NULLABLE | `MARKET_CLOSED` or `SOURCE_TIME_UNVERIFIED` |
| `snapshot_timestamp` | TIMESTAMP | NULLABLE | Partition key: snapshot creation time |
| `source_timestamp` | TIMESTAMP | NULLABLE | Timezone-aware snapshot observation time |
| `cycle_id` | STRING | NULLABLE | Publication cycle identifier |
| `run_id` | STRING | NULLABLE | GitHub Actions RUN_ID / Execution run ID |
| `git_sha` | STRING | NULLABLE | Exact Git commit hash |
| `writer_id` | STRING | NULLABLE | Authorized writer identifier (`market_bot`) |

---

## 2. `market_news_sentiment`
- **Table ID**: `fno-angel-prod-1790444589.fno_predictions.market_news_sentiment`
- **Time Partitioning**: `DAY` on `timestamp`
- **Clustering Fields**: `['symbol', 'news_type']`
- **Write Disposition**: `WRITE_APPEND`

| Column Name | Type | Mode | Description |
|---|---|---|---|
| `symbol` | STRING | NULLABLE | Underlying symbol |
| `title` | STRING | NULLABLE | Headline / disclosure title |
| `sentiment` | STRING | NULLABLE | Positive, Negative, or Neutral |
| `tone_score` | FLOAT | NULLABLE | Continuous sentiment score (-1.0 to 1.0) |
| `impact_rating` | STRING | NULLABLE | Rating classification |
| `source` | STRING | NULLABLE | Publishing domain / news wire |
| `news_type` | STRING | NULLABLE | Regulatory, Corporate, or Wire news |
| `filing_type` | STRING | NULLABLE | Exchange filing categorization |
| `source_count` | INTEGER | NULLABLE | Number of corroborating sources |
| `source_agreement_pct` | FLOAT | NULLABLE | Corroboration consensus % |
| `severity_level` | INTEGER | NULLABLE | Impact scale |
| `source_tier` | STRING | NULLABLE | Domain authority tier |
| `positive_prob` | FLOAT | NULLABLE | Probability positive |
| `negative_prob` | FLOAT | NULLABLE | Probability negative |
| `already_priced_in_prob` | FLOAT | NULLABLE | Priced-in probability |
| `market_confirmation` | STRING | NULLABLE | Flow confirmation |
| `expected_move_band` | STRING | NULLABLE | Expected move magnitude |
| `source_url` | STRING | NULLABLE | Source article URL |
| `canonical_url` | STRING | NULLABLE | Canonical link |
| `verified_catalyst` | BOOLEAN | NULLABLE | True if confirmed by primary filing |
| `timestamp` | TIMESTAMP | NULLABLE | Partition key: publication timestamp |
| `run_id` | STRING | NULLABLE | Lineage: Run ID |
| `git_sha` | STRING | NULLABLE | Lineage: Git commit SHA |
| `writer_id` | STRING | NULLABLE | Lineage: Writer ID |
| `source_timestamp` | STRING | NULLABLE | Lineage: Observation timestamp |
| `cycle_id` | STRING | NULLABLE | Lineage: Publication cycle identifier |

---

## 3. `next_day_gap_predictions`
- **Table ID**: `fno-angel-prod-1790444589.fno_predictions.next_day_gap_predictions`
- **Time Partitioning**: None
- **Clustering Fields**: None
- **Write Disposition**: `WRITE_APPEND`

| Column Name | Type | Mode | Description |
|---|---|---|---|
| `prediction_date` | DATE | REQUIRED | Prediction session date |
| `predicted_at_ist` | STRING | REQUIRED | Prediction time string in IST |
| `symbol` | STRING | REQUIRED | Underlying symbol |
| `target_date` | DATE | REQUIRED | Target session date for opening gap |
| `side` | STRING | REQUIRED | Gap direction (`GAP_UP` or `GAP_DOWN`) |
| `spot_ltp` | FLOAT | REQUIRED | Spot price at prediction time |
| `target_strike` | STRING | REQUIRED | Target strike |
| `contract_symbol` | STRING | REQUIRED | Exact option contract identifier |
| `entry_ltp` | FLOAT | REQUIRED | Option entry LTP |
| `expected_gap_pct` | FLOAT | REQUIRED | Forecasted gap % |
| `conviction_pct` | FLOAT | REQUIRED | Model conviction % |
| `stop_loss_ltp` | FLOAT | REQUIRED | Paper stop-loss level |
| `target_ltp` | FLOAT | REQUIRED | Paper target level |
| `rationale` | STRING | REQUIRED | Forecast rationale summary |
| `news_catalyst` | STRING | NULLABLE | Headline / event catalyst |
| `dollar_gamma` | FLOAT | NULLABLE | Option dollar gamma measure |
| `actual_open_ltp` | FLOAT | NULLABLE | Actual LTP at morning 09:15 open |
| `actual_return_pct` | FLOAT | NULLABLE | Actual % return on paper contract |
| `outcome` | STRING | NULLABLE | `WIN`, `LOSS`, or `PENDING_OPEN` |
| `reconciled_at_ist` | STRING | NULLABLE | Timestamp of reconciliation |
| `run_id` | STRING | NULLABLE | Lineage: Run ID |
| `git_sha` | STRING | NULLABLE | Lineage: Git commit SHA |
| `writer_id` | STRING | NULLABLE | Lineage: Writer ID |
| `source_timestamp` | STRING | NULLABLE | Lineage: Observation timestamp |
| `cycle_id` | STRING | NULLABLE | Lineage: Publication cycle identifier |

---

## 4. `prediction_calibration_log`
- **Table ID**: `fno-angel-prod-1790444589.fno_predictions.prediction_calibration_log`
- **Time Partitioning**: `DAY` on `timestamp`
- **Clustering Fields**: None
- **Write Disposition**: `WRITE_APPEND`

| Column Name | Type | Mode | Description |
|---|---|---|---|
| `timestamp` | TIMESTAMP | NULLABLE | Partition key: Calibration time |
| `cycle_number` | INTEGER | NULLABLE | Monotonic cycle sequence number |
| `top10_hit_rate_pct` | FLOAT | NULLABLE | Hit rate of Top 10 predictions % |
| `recall_at_10` | FLOAT | NULLABLE | Recall at rank 10 |
| `mean_rank_of_top10` | FLOAT | NULLABLE | Average rank position |
| `predicted_top10` | STRING | NULLABLE | JSON array of predicted top 10 contracts |
| `actual_top10` | STRING | NULLABLE | JSON array of actual top 10 movers |
| `hits` | STRING | NULLABLE | JSON array of hit contracts |
| `misses` | STRING | NULLABLE | JSON array of missed contracts |
| `miss_root_causes` | STRING | NULLABLE | JSON breakdown of error attribution |
| `updated_weights_json` | STRING | NULLABLE | JSON map of recalibrated multi-factor weights |
| `run_id` | STRING | NULLABLE | Lineage: Run ID |
| `git_sha` | STRING | NULLABLE | Lineage: Git commit SHA |
| `writer_id` | STRING | NULLABLE | Lineage: Writer ID |
| `source_timestamp` | STRING | NULLABLE | Lineage: Observation timestamp |
| `cycle_id` | STRING | NULLABLE | Lineage: Publication cycle identifier |

---

## 5. `cycle_status`
- **Table ID**: `fno-angel-prod-1790444589.fno_predictions.cycle_status`
- **Time Partitioning**: `DAY` on `created_at`
- **Clustering Fields**: `['status', 'sink']`
- **Write Disposition**: `WRITE_APPEND`

| Column Name | Type | Mode | Description |
|---|---|---|---|
| `cycle_id` | STRING | REQUIRED | Unique publication cycle identifier |
| `run_id` | STRING | REQUIRED | Lineage: Run ID |
| `git_sha` | STRING | REQUIRED | Lineage: Git commit SHA |
| `sink` | STRING | REQUIRED | Destination table / sink name |
| `status` | STRING | REQUIRED | Status: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `NOT_DUE` |
| `records_count` | INTEGER | NULLABLE | Total rows written to sink |
| `error_message` | STRING | NULLABLE | Error message if status is FAILED |
| `created_at` | TIMESTAMP | REQUIRED | Partition key: status record timestamp |


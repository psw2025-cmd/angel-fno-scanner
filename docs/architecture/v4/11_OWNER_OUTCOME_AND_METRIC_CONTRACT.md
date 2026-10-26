# Owner goal => measurable contract

Owner wants strongest possible India F&O and multibagger research, improved risk-adjusted performance, low daily manual effort, 24x7 cloud operations, full transparency and durable agent continuity. These are objectives, not promised returns.

## Decision metrics

**Options**: alert issue time, forecast source time, entry quote availability, matched contract identity (exchange, underlying, strike, type, expiry), bid/ask, slippage, simulated filled size, PAPER realized P&L, max loss per day and drawdown, turnover, costs, benchmark same-window, calibrated probability, outcomes linked by prediction_id. Separate generated forecast from observed trade and verified outcome. No P&L from hypothetical intrabar highs unattainable at executable quotes. No live orders.

**Equity**: 2x/3x/5x/10x/20x absolute thresholds over 3/6/12 months; for rare 10x/20x 24/36-month study where data support. Count future horizon-matured labels, precision@K, recall@K, NDCG, Brier score, calibration, average lead time, hit time, right censoring, transaction-cost-and-liquidity-adjusted alpha versus date-matched Nifty 500 TRI and sector/size cohorts, max drawdown, exposure concentration, turnover, negative tail loss, unrecoverable suspensions. Avoid cherry-picking. Show confidence intervals and base rate. No 100% prediction claim.

**Research**: authorized sources include NSE/BSE official market data, exchange announcements, SEBI filings, corporate reports, verified statements, economic/sector news, market microstructure, license-permitted broker feed. Record source URL/provider, terms/license, observed_at, published_at, ingested_at, valid_from/to and immutable hash. Public comments/social/news can become low-trust *features* with corroboration; never authoritative price or order triggers. Strict chronological arrival rules.

**Ops**: per-market-session complete execution %, quote age, 219-universe identity %, reconciled data rows %, CI coverage by exact SHA, unattended cloud health %, median recovery time, stale incident count, cloud spend and data-access expiry. Notify on pending decisions; no daily manual clicks for routine healthy operations.

## Stop conditions

Stop model promotion if source license not documented, survivor-only universe, unresolved delistings, failed corporate action adjustments, leaked label time, <100 eligible mature outcomes, unverifiable forward receipt, benchmark missing, unacceptable drawdown, or distribution shift. Continue recording PAPER evidence without live-order permission.

## Reporting

Monthly owner dashboard: expected gains are **probabilistic estimates** with uncertainty; separate backtest results, prospective PAPER results and actual investable performance. Do not use retrospective top-gainers as a substitute for predicted winners. CI PASS does not imply investment success.
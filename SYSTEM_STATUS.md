# SYSTEM STATUS — Phase 2

**Status: BLOCKED for real-data paper-close certification.** The offline synthetic fixture workflow passed, but this is not real market proof.

## Observed blockers
- GitHub-hosted NSE public option-chain API returned HTTP 404.
- Browser-header / same-session cookie attempt returned NSE homepage HTTP 403.
- Google Cloud authentication received neither workload identity provider nor credentials JSON.
- Repository/environment secret names and values cannot be enumerated with the currently available GitHub connector. No broker login has been observed.

## Broker pivot
`phase2/angel_readonly.py` implements fail-closed SmartAPI authentication and **read-only** FULL market-data quotes. No order placement methods are invoked. Broker quotes are not by themselves an authenticated complete historical option-chain or officially published closing settlement. The existing `phase2/real_close.py` NSE integration must not be silently replaced with an unverified or incomplete broker feed. The next implementation step is verified symbol-token/expiry mapping, option-chain completeness, exchange timestamp checks, and explicit provenance before enabling broker as the close source.

## Heuristic
`V1_Heuristic_Model_snapshot_v2-not-trained` validates PCR as a finite value in [0,10]. For CE, imbalance = clamp((PCR-1)/0.5,0,1); for PE, imbalance = clamp((1-PCR)/0.5,0,1). Volume quality = min(1, log1p(volume)/log1p(10000)). Liquidity condition is OI >= 1000, volume >= 100, spread_pct <= 2. Score = round((0.7*imbalance + 0.3*volume_quality)*(1 if liquid else 0),8). This is a heuristic, not trained predictive ML.

## Storage and safety
`phase2/local_publisher.py` produces a BigQuery MERGE-formatted **non-insert** receipt. The workflow is configured to commit independently verified receipts to `data/paper_ledger/<prediction_hash>.json` only after real-source validation succeeds. No real receipt has been observed. `PAPER_MODE=1`, `LIVE_ORDER_AUTHORITY=0` remain mandatory. No existing production BigQuery table may be written by this workflow.

## One-time owner setup
Use the actual existing repo secret names: `ANGEL_API_KEY`, `ANGEL_CLIENT_CODE`, `ANGEL_PIN`, `ANGEL_TOTP_SEED`. Optional cloud identity: `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT`, configured only with a dedicated sandbox-limited service account. Never commit credentials, tokens, or raw authentication responses.

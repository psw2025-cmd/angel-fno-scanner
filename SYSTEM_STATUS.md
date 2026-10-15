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

## Local headless runner (Windows)
`run_phase2_local.py` is committed on `test-framework`. It reads the owner's local `.env`, forces PAPER_MODE=1 and LIVE_ORDER_AUTHORITY=0, authenticates through read-only Angel SmartAPI, validates an owner-supplied locally verified NFO contract manifest, and captures `data/raw_snapshot.json` with a SHA-256 digest. It deliberately fails closed before publishing a prediction because individual FULL broker quotes have not yet been demonstrated to supply a complete synchronized chain, verified bid/ask, observed PCR and official close. The requested automatic receipt push is **not certified or enabled** until those validations exist; `--push` does not override them. No broker secrets, JWT, refresh tokens or TOTP values may be committed. Cloud broker authentication was not observed to fail: cloud NSE access and cloud GCP authentication failed, while broker credentials were not established.

## Auto-token and quote-snapshot runner upgrade
`phase2/angel_instruments.py` downloads Angel's OpenAPIScripMaster JSON and automatically selects paired CE/PE tokens for the nearest non-expired NIFTY and BANKNIFTY NFO expiry. `run_phase2_local.py --push` fetches read-only FULL broker quotes, saves a private raw snapshot, validates observed OI, volume and bid/ask, computes **selected-strike PCR** (not full-chain PCR), ranks using the snapshot heuristic, verifies the SHA-256 receipt, and attempts a Git commit/push to `test-framework`. In PAPER mode the official-close requirement is waived **only for explicitly labeled quote-snapshot validation**, not for claims of official close or production readiness. The script fails closed if credentials, instrument data, quotes or necessary fields are missing. Actual local execution and successful push have not yet been observed.

## Local bounded retry wrapper
`run_and_force_push.ps1` invokes the local paper runner with `PAPER_MODE=1` and `LIVE_ORDER_AUTHORITY=0`, retries transient failures up to ten attempts with bounded backoff, checks receipt safety/hash shape, confirms the receipt is in HEAD, and independently compares local HEAD with `git ls-remote origin refs/heads/test-framework`. A success message is issued only after remote SHA equality. The wrapper deliberately **does not** delete `.git/index.lock` (which may belong to an active Git process), discard local edits, resolve conflicts automatically, or perform `--force` pushes that could overwrite others' commits. Divergent history fails safely with a diagnostic. It is a finite recovery helper, not an unkillable daemon; successful execution still requires local credentials, valid quotes and remote write access.

## Angel One GitHub-only paper workflow (2026-10-15)
Architecture authority: Angel One SmartAPI read-only quotes, using existing GitHub Actions secrets ANGEL_API_KEY, ANGEL_CLIENT_CODE, ANGEL_PIN and ANGEL_TOTP_SEED. Dedicated workflow `.github/workflows/phase2-angel-paper.yml` runs on test-framework; `PAPER_MODE=1`, `LIVE_ORDER_AUTHORITY=0`. Runner no longer requires local `.env` when GitHub environment secrets are provided. GitHub Actions run 38737193069 was observed queued then in_progress; broker login, receipt and SHA verification are NOT yet certified. NSE legacy workflow is not a fallback. The workflow records a broker quote capture, not official settlement, and a local BigQuery-formatted artifact, not a BigQuery insertion. Any missing secret or login failure must be resolved from actual run evidence without exposing values.

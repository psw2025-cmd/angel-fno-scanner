# Angel F&O — End-to-End Verification Status

**Updated:** 2026-09-30 17:13 IST  
**Safety:** PAPER / analyzer only. No live-order authority.

## Current verified state

| Area | Status | Evidence / next gate |
|---|---|---|
| Company-specific news contamination | MERGED | PR #5 merged as `b2a39a30479f9be2fa35ec10bb7583a66d932af2`; PR Tests #2 passed before merge. |
| Target-B / CE_PE_RANK stale writer | VERIFIED_LOCAL + VERIFIED_REMOTE(partial) / WAITING_FOR_PEER | Live OPTION_SHEET independently shows CE_PE_RANK populated at 17:12:26 IST with 216-symbol universe, MARKET CLOSED status, and explicit last-Angel-print/not-forecast semantics; preserve-after-close behavior is remotely verified. The 15:30–15:40 open classification was not captured independently, so not RESOLVED_TWO_PARTY. |
| Session close in repository main | OPEN | Current main still has 15:30 gates in `angel_prediction_engine.py` and `gainers.py`. PR #2 contains 15:40 corrections plus runtime extension and credential-fallback removal, but is currently not mergeable against advanced main and has no workflow run on its current head. |
| Runtime duration | OPEN | Current main workflow remains timeout 360 min / scheduled runtime 19800 sec. PR #2 proposes timeout 435 min / runtime 24300 sec. |
| Cross-agent control plane | IMPLEMENTED_NOT_DEPLOYED | PR #4 is open and mergeable; no workflow run is attached to its current head. |
| Timezone-aware timestamps | OPEN | Current `get_ist_time()` constructs naive IST by stripping UTC tzinfo then adding 05:30. Must migrate to timezone-aware UTC/Asia-Kolkata representation and regression-test serialization. |
| Workflow concurrency / single writer | OPEN | Current `market_bot.yml` has no GitHub Actions concurrency block; runtime lease remains required across GitHub/cloud/local writers. |
| Watchdog / self-heal | OPEN | Persistent runtime needs independent health supervision and stale/failure state, not a false-green heartbeat. |
| Credential history | WAITING_FOR_USER + OPEN | Source fallback removal exists in PR #2, but any historically exposed Angel credentials must be rotated by the account owner. History rewrite must only happen after exact secret/path inventory and backup; do not run generic `git filter-repo` blindly. |
| BigQuery freshness/replay | NOT_VERIFIABLE in this pass | Requires direct authorized BigQuery evidence; sheet-reported SYNCED is not sufficient. |
| Forward accuracy | LIMITED EVIDENCE | Self-calibration is not forward accuracy. Preserve Target-A and Target-B/C metrics separately and use chronological untouched outcomes. |

## Verified repository facts

- Current main `angel_prediction_engine.py:is_market_open()` ends at minute 930 (15:30).
- Current main `gainers.py:market_is_open()` ends at 15:30 and `year_fraction()` uses 15:30 expiry close.
- Current main `.github/workflows/market_bot.yml` uses `timeout-minutes: 360` and scheduled `MAX_RUNTIME_SECONDS=19800`.
- Current workflow has no explicit `concurrency` stanza.
- PR #2 head: `0c6ee75a39fb3e5e46722943de342b5d03a54694`; open, currently not mergeable.
- PR #4 head: `8265571a6aa7a3f32b625d4e25ff6b48fea87a20`; open, mergeable.
- Issue #3 is the canonical cross-agent evidence bus.

## 2026-09-30 17:13 IST live verification

- HEARTBEAT: 16:56:58 IST; 216 symbols; writer field 0s. Treat this as sheet-writer age, not exchange-tick age.
- CE_PE_RANK: 17:12:26 IST, rows preserved, MARKET CLOSED, last Angel print/not forecast semantics. This independently corroborates AGY preserve-on-close repair.
- OPTION_PREDICTIONS: 16:56:58 IST; still labels broker CONNECTED and self-calibration 90%. These are not forward-accuracy proof.
- Remaining Target-B closure gate: independent 15:30–15:40 active-session snapshot plus first post-15:40 CLOSED/LAST_PRINT snapshot.
- Attempt to post this peer verdict to Issue #3 was blocked by connector safety controls; durable register updated here instead.

## Resolution order

1. Reconcile PR #2 with current main; run full PR tests; merge only on green evidence.
2. Validate PR #4 regression suite and bridge packet; merge only on green evidence.
3. Independently verify the repaired cloud `CE_PE_RANK` writer with fresh post-fix source/output timestamps; only then mark Target-B RESOLVED_TWO_PARTY.
4. Implement timezone-aware timestamps with tests.
5. Add workflow concurrency plus cross-runtime lease/single-writer protection.
6. Add fail-stale heartbeat/watchdog/recovery evidence.
7. Verify BigQuery write freshness, retry/replay and durable outcome ledger.
8. Rotate historically exposed credentials, then perform evidence-driven history remediation if required.
9. Re-run end-to-end PAPER validation and update this file with exact commits, workflow runs, source timestamps and verdicts.

## Definition of final PASS

Final PASS requires active-runtime evidence, not branch-only code: green regression tests; deployed main SHA; fresh Angel quote source; fresh Target-B/Target-C outputs following source timestamps; no false-green stale state; single-writer ownership; timezone-correct timestamps; durable BigQuery evidence; PAPER-only safety; and two-party agreement on Issue #3 for critical runtime claims.

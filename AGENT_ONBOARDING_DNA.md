# Agent onboarding: Phase 2/3 and Option DNA v1

## Trust boundary
`main` is default-branch workflow registration; scheduled jobs check out `test-framework` and commit only paper ledger artifacts. GitHub Secrets are environment scoped to `phase2-paper`. `PAPER_MODE=1` and `LIVE_ORDER_AUTHORITY=0` are mandatory in CI and Python. `AngelReadOnlyProvider` calls FULL market-data only. Never add order placement or claim fills.

## Pipeline
Phase 2: authenticated NFO instrument master → exact token/symbol FULL quotes → raw snapshot SHA-256 → selected-contract OI/PCR, volume, spread and heuristic ranking → canonical prediction hash → receipt, immutable exact-token entry manifest and immutable Option DNA ledger. Phase 3: traverse receipt Git history, validate previous weekday (or explicit labelled same-day engineering test), canonical hashes and manifest linkage → re-quote identical NFO token → theoretical per-unit long mark `current_bid - original_entry_ask`, percent `100 * delta / entry_ask` → immutable report and linked comparison DNA ledger. Dashboard renders verified evidence; unweighted sum of per-unit marks is not portfolio PnL.

## Option DNA definitions (transparent, exploratory thresholds)
Spread percent = `200*(ask-bid)/(ask+bid)`. Flag `WIDE_SPREAD_3PCT` at >=3%. A **true shock** requires prior same-token spread, current >=2x prior and increase >=1 percentage point. Volume/OI ratio = `tradeVolume/openInterest` when OI positive: >=3 high turnover relative to OI, <=0.05 low turnover. This ratio is NOT an OI change or verified divergence; prior OI enables separate `OI_FALL_20PCT_WITH_VOLUME` when OI falls >=20% with current volume >=100. Compare timestamps/session before treating any apparent movement as market signal. FULL quotes do not establish verified IV or Theta: both must remain null and status `UNAVAILABLE_NO_VERIFIED_IV_GREEKS_OR_TIME_SERIES`. No inferred decay from two unadjusted option prices.

Selected-strike put/call OI ratio >=1.5 emits `POTENTIAL_BOTTOM_WATCH_OI_IMBALANCE_ONLY`; <=0.67 emits `POTENTIAL_TOP_WATCH_OI_IMBALANCE_ONLY`. These are explicitly **unconfirmed hypotheses**, not tops, bottoms, predictions or trained models; they lack underlying trend, full chain, validated historical labels and out-of-sample precision. The thresholds require forward calibration and regime segmentation before use as decisions.

## Provenance, replay, learning
`data/anomaly_logs/dna_<prediction_hash>.json` is Phase 2 evidence linked to original source SHA; `comparison_<report_sha256>.json` is Phase 3 evidence linked to immutable PnL report. Do not overwrite conflicting files. Never use today's future labels in today's features. Before any self-learning: collect market-calendar-aware timestamped features, quote freshness, contract metadata, underlying price/volume, IV and Greeks from licensed verified feeds, forward outcome labels, walk-forward splits, class balance, costs and liquidity gates. Keep paper-only and measure false positive rates by regime. Do not auto-promote heuristic thresholds.

## Failure modes
GitHub schedules run only from default branch and may be delayed; concurrent branch pushes can conflict. Never reintroduce a push-trigger loop for Phase 2. A broker timestamp at 15:40 returned at 20:26 is stale market-close data, not live movement. Missing prior DNA is `LEGACY_ENTRY_DNA_UNAVAILABLE`, not zero anomalies. Holiday calendar, exact quote freshness and dashboard main-vs-ledger synchronization are separate acceptance gates. Preserve Git SHA, job URL, hashes, and test output with every release.

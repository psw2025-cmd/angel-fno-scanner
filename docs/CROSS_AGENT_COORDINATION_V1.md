# Cross-Agent Coordination V1

Canonical bus: GitHub Issue #3.

## Purpose

AGY CLI is the local Windows/Power BI/runtime verifier. ChatGPT is the independent GitHub/Sheets/BigQuery/artifact verifier. Neither lane may self-certify a critical item.

## Consensus rule

A critical issue is `RESOLVED_TWO_PARTY` only when all are true:

1. the change is active in the intended runtime;
2. the claimant supplies reproducible evidence;
3. the peer checks a materially independent evidence source;
4. both observations refer to compatible timestamps/SHA/runtime identity;
5. no contradiction remains;
6. regression protection exists where practical.

If any observation conflicts, set `DISPUTED` and continue investigation. Do not average contradictory evidence into a green score.

## Statuses

- `OBSERVED`
- `OPEN_AUTO_FIXABLE`
- `IMPLEMENTED_NOT_DEPLOYED`
- `VERIFIED_LOCAL`
- `VERIFIED_REMOTE`
- `DISPUTED`
- `WAITING_FOR_PEER`
- `WAITING_FOR_USER`
- `RESOLVED_TWO_PARTY`

## Evidence separation

Always distinguish:

- **OBSERVATION** — directly measured.
- **CLAIM** — an agent's interpretation.
- **INFERENCE** — conclusion from observations.
- **IMPLEMENTATION** — code/config changed.
- **VERIFIED_AFTER_STATE** — active runtime independently rechecked.

A screenshot or HTML dashboard is not sufficient proof of process health, source freshness, or Power BI connectivity.

## Operational production target

The system cannot promise literal zero software defects or 100% market prediction accuracy. Production-grade means:

- no silent critical failure;
- fail-closed behavior;
- no false-green health;
- single-writer data authority;
- 216/216 coverage gate before destructive publication;
- durable retry/replay and recovery where safe;
- timestamp-correct immutable evidence;
- continuous monitoring;
- automated regression detection;
- controlled model promotion/rollback based on untouched forward data.

## Prediction-learning governance

Keep two separate targets:

- **Target A:** next-session underlying opening gap direction/magnitude.
- **Target B:** exact CE/PE contract extreme-premium ranking.

Track CE and PE separately. Use chronological train/validation/untouched-forward partitions. Never promote a model because of self-calibration or same-batch matching. Never use post-forecast information as an input to the forecast being scored.

Required metrics include Top-1/Top-3/Top-5 capture, NDCG where useful, opening-gap direction accuracy, gap MAE/RMSE, capture ratio versus best liquid/executable contract, calibration/Brier where applicable, and executable PAPER P&L using bid/ask and slippage assumptions.

## Canonical workflow

1. AGY runs `tools/agy_cross_agent_packet.ps1` for a local claim.
2. AGY posts the packet to Issue #3 automatically with `-PostToGitHub`.
3. ChatGPT reads the new packet and independently verifies GitHub/Sheets/BigQuery/available artifacts.
4. ChatGPT posts a peer verdict to Issue #3.
5. If verdict is DISPUTED, AGY reproduces the discrepancy locally and posts a new packet.
6. Repeat until evidence converges.
7. Only then use `RESOLVED_TWO_PARTY`.

## Safety

PAPER/analyzer only. This protocol never authorizes live order placement. Never place secrets in packets or issue comments.

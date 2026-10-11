# TODAY — 2026-10-11 16:15 IST (Sunday, market CLOSED)

PAPER only. Sources checked this hour: GitHub `main` `4ebeae6`, GitHub Actions run `38131538889`, and a full xlsx download of OPTION_SHEET. BigQuery SQL tool is **not connected**. Power BI and n8n were **not** seen.

## Proven on the live sheet (download, not the 6 Oct note)

| Fact | Value |
|---|---|
| FORENSIC_LIVE symbols | **219 unique**, last row time **2026-10-10 16:47:33** |
| Formula GATE-01 / 03 / 04 / 05 | PASS |
| GATE-02 | **MARKET CLOSED** |
| GATE-06 | **PASS 200/200** (not the old 216 formula) |
| GATE-07 | PASS, 0 high-momentum alerts while closed |
| Overall formula line | **MARKET CLOSED — alerts are not live** |
| PUBLICATION_STATUS | **VERIFIED** at 2026-10-10 16:47:33, run `38047639312`, git `d36aede`, writer `market_bot`, digests present |
| WRITE_PROVENANCE last row | same run, `prediction_cycle`, 219 |
| HEARTBEAT fetch | 2026-10-10 16:43:58, label `CONNECTED_ANGEL_SMARTAPI`, stream cell HEALTHY |
| Drive file modified | 2026-10-10 16:50 IST. **Not touched today.** |

## Still not true / not proven

| Claim | Truth |
|---|---|
| HEARTBEAT HEALTHY + CONNECTED means the market is live | **False.** Formula Checks correctly says closed. Sunday has no new print. |
| Self-calibration 0.90 = trading accuracy | **False.** That cell is self-calibration, not a forward test. |
| PRE_BREAKOUT `+545%` | **Display bug.** FORENSIC stores futures change as `5.45`. Do not use PRE_BREAKOUT. |
| `data/summary.md` is today's book | **Stale.** Generated `2026-10-09T10:09:46Z`. |
| `operator/STATUS.json` on main (6 Oct GREEN) | **Stale.** |
| BigQuery still has provenance | **Not re-queried.** Sheet C2 says sync `2026-10-10 16:47:33`. No independent BQ read today. |
| Power BI PID / n8n 11 workflows | **Not seen from here.** |
| NASA daily proof is green | **Failed** today. Run [38131538889](https://github.com/psw2025-cmd/angel-fno-scanner/actions/runs/38131538889). Error: `GCS evidence BLOCKED or FAIL. Configure WIF... BigQuery ledger readback remains unimplemented.` Encoding Safety on the same SHA **passed**. |

Trader use Monday: PAPER only. Trust FORENSIC_LIVE + PUBLICATION_STATUS VERIFIED + Formula Checks MARKET CLOSED/open line. Ignore PRE_BREAKOUT percents and HEARTBEAT HEALTHY when the session is closed.

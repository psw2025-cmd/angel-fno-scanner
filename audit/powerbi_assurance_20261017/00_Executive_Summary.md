# Power BI Production Assurance Audit - Executive Summary

- Solution: ANGEL_FNO_MONITOR (PBIP, TMDL model + PBIR report)
- Audited: 2026-10-17, 14:12 to 14:51 IST
- Model audited as loaded: origin/main 518ca5770efc63f5ba2a868a8ee854f1d838baee
- Safety state: PAPER / ANALYZER = ON, LIVE ORDER AUTHORITY = OFF, REAL BROKER ORDERS = 0. The audit was read-only on all live systems.

## Verdict: FAIL (confidence 96%)

13 of 20 readiness criteria fail, 3 pass with risks, 4 pass (see 10_Production_Readiness.csv).
The dashboard cannot be used as a source of truth for the market state.

## Why (each item has an Evidence ID in 11_Evidence_Register.csv)

1. R01 Data on screen is 18 days old. All model partitions were refreshed 2026-09-29; file last saved 2026-09-30 (E-03, E-12).
2. R02 The GitHub JSON feed that Power BI reads has been dead since 2026-10-09; market_bot.yml last ran 2026-10-13 and failed (E-06, E-10, E-11).
3. R03 Heartbeat, ForensicLive, CERank and Calibration are constants pasted into the model. They cannot refresh and display HEALTHY / 216 symbols / 0 s (E-03, E-05, E-12).
4. R04 Universe Health tests 216. The engine contract is 219 (E-05, E-13). Loaded Live Symbols is 171.
5. R05 Six Top Gap measures raise an error on the live engine, which breaks page 6 (E-05, E-17).
6. R06 No executable winner is shown. The raw leader is a Rs 5 premium, up 9900% (E-05, E-12).
7. R09 (inference) PAPER_ALERT_LOG header change will break the Rename step on the next refresh (E-08, E-18).
8. R10 BigQuery snapshot_timestamp is IST wall time labelled UTC (E-09).

## Verified working

- Power BI Desktop (PID 23416) and msmdsrv (PID 11740, port 59161) alive (E-01).
- The opened PBIP is content-identical to main, 111 of 111 files (E-02).
- Parser counts match the live engine: 59 measures (E-04, E-14).
- 0 unresolved visual fields; liquidity PASS 93 + REJECT 78 = 171 rows (E-05, E-14).

## Changes on this branch (audit/powerbi-assurance-20261017)

- Six Top Gap measures rewritten (scalar flag instead of a table-valued IF). Verified on the live engine through a query-scoped DEFINE MEASURE, with no model change: Top Gap Up = KALYANKJIL (+1.53%), Down = BAJFINANCE (-1.61%) (E-17).
- Universe Health now tests 219.
- tests/test_powerbi_model_contract.py: 7 tests; 3 fail on the old file and all 7 pass on the fix (E-21). Full suite: 314 passed.
- tools/powerbi_assurance_audit.py regenerates every CSV and diagram from the repo and raw evidence.
- The fix is NOT live in the owner's open dashboard until Desktop reopens the fixed PBIP and refreshes.

## NOT VERIFIED

- A real refresh was not executed (it would overwrite the owner's open dashboard state).
- Power BI Service publication or schedule: no evidence found.
- Timestamp meaning inside the GitHub JSON.
- Pages were checked for error cards, not pixel by pixel.

## Decisions needed from the owner

- A02 new data source for the model (repoint to the live Sheet or BigQuery).
- A06 executable-quality thresholds (spread, OI, volume).
- A12 access model (public Sheet / repo).
- A14 authoritative copy of the PBIP (24 copies exist).
- A15 Desktop only or Power BI Service.

## Handoff (AGENTS.md section 32)

- RUN_ID: powerbi-assurance-20261017
- AGENT: Cursor agent
- MAIN_SHA: 518ca5770efc63f5ba2a868a8ee854f1d838baee
- WORKING_BRANCH: audit/powerbi-assurance-20261017
- STATUS: A04, A05, A13 IMPLEMENTED_NOT_DEPLOYED; the rest OPEN or WAITING_FOR_USER
- PEER_VERIFICATION_REQUIRED: yes (two-party rule); not RESOLVED_TWO_PARTY
- NEXT_OWNER: owner approves the PR; then Power BI refresh test
- NEXT_EXACT_ACTION: reopen the fixed PBIP, refresh, and re-run `python tools/powerbi_assurance_audit.py`

# PM-008 — PowerBI Refresh Failure & msmdsrv Lock State

## 1. Problem Statement & Root Cause
Power BI Desktop instances on Windows (`DESKTOP-DM6NHPI`) utilize an embedded SQL Server Analysis Services process (`msmdsrv.exe`). If Power BI crashed or was terminated abruptly during a data model refresh, stale lock files in `**/.pbi/` and zombie `msmdsrv.exe` processes prevented subsequent file loads and refresh triggers.

## 2. Impact
Stale market data visualization in Power BI Desktop dashboards and failed automated refresh sequences.

## 3. Resolution & Commit
- Added `**/.pbi/` and `*.pbix` to `.gitignore` to prevent binary lock files and model files from entering git.
- Documented process verification commands (`Get-Process -Name '*msmdsrv*'`) in `docs/AGENT_EXPERT_ROUTING.md`.
- Power BI local process management assigned exclusively to AGY.

## 4. Prevention & Forensic Gates
- Verified by proof ledger check P-21 (`PowerBI Refresh & Process Safety`).
- Power BI telemetry monitored in `LIVE_DASHBOARD_FOR_USER.md`.

# Angel FNO Evidence Operations Dashboard

## Run locally

From the scanner repository in PowerShell:

```powershell
.\ops_dashboard\run_dashboard.ps1
```

Open `http://127.0.0.1:8765/`. Stop with `Ctrl+C`. The server binds to loopback only and is not remotely hosted or deployed.

## Authentication and trust boundary

The server verifies that the owning Windows process for a loopback HTTP client has the same Windows SID as the dashboard process. It then issues an HttpOnly, SameSite=Strict, process-memory-signed session cookie. A server restart invalidates cookies; the same Windows-user check re-authenticates the local browser. This does not authenticate remote users and is unsuitable for LAN/Vercel exposure. Hosting beyond localhost requires an approved identity provider, HTTPS termination, CSRF defenses, secrets management, and a reviewed authorization model.

GitHub reads use the existing `gh` CLI identity on the server. Tokens are never returned to browser code or logs. Cloud workers may load existing credentials server-side through the repository credential loader. No token, key or secret value is returned to the browser.

## Collectors and data policy

- Local Git: HEAD, branch, `git status`, origin/main SHA.
- GitHub: repository metadata, last 20 workflow runs, and open PR metadata via read-only `gh` commands.
- Local runtime: process names/PIDs/creation times for selected services; no command lines or environment values.
- Local monitor: `system_live_telemetry.json`; file mtime controls freshness. An old file's embedded HEALTHY value is displayed only as a historical claim; current health becomes UNKNOWN.
- Repo structure: tracked source paths, Python AST imports and conservative uniquely-resolved local calls; source edges are SOURCE_DERIVED, co-change edges HISTORY_CORRELATED.
- Google Sheets and BigQuery collectors perform authenticated metadata/sample GET reads. Access PASS does not prove market freshness, Sheet/BQ parity or trading readiness. Failures stay UNKNOWN/FAIL.
- Power BI model freshness, deployed/runtime SHA, Firebase, Vercel, Google Tasks, Analytics and YouTube remain unverified unless their own current evidence is present. No cloud mutations are issued by these dashboard collectors.

Snapshots are stored as compact JSONL under `%LOCALAPPDATA%\AngelFNO\dashboard\evidence`, retained for 30 days, with a 16 MB daily-file cap. Issue exports are stored under `%LOCALAPPDATA%\AngelFNO\dashboard\exports`; export history is retained there. Repository source remains read-only.

Refresh: browser overview every 15 seconds; GitHub reads are cached for 60 seconds; repo graph/history are cached for 5 minutes. Static analysis is limited by file count and byte budgets. No service is called continuously when the app is closed.

## Safety / limitations

No broker-order API is used. No Sheets/BigQuery write, merge, push, deployment, IAM change, package install, or task execution is performed. Static/synthetic artifacts are not classified as runtime evidence. The dashboard does not infer production health from stale snapshots. No hosted address or cost is claimed: this is a local app and incurs no hosting expense; GitHub API rate limits and local disk retention apply. Cloud observations are bounded and cached; inspect each observation timestamp and scope before interpreting PASS.

## Progress

The machine-readable phase state is `ops_dashboard/progress.json`. It records implemented, validated, blocked, and incomplete phases and is updated as work proceeds.


## Operational troubleshooting — 2026-10-21

A working localhost page proves only that the UI is reachable. Require current broker feed timestamps, authorized writer evidence, prediction freshness and independent publication readback before declaring live operation. Keep PAPER_MODE=1 and LIVE_ORDER_AUTHORITY=0.

The supervisor uses the scheduled repository venv. Windows requires tzdata for Asia/Kolkata. Agent CLI readiness alerts are now opt-in via --agent-alerts; they must not block the market health loop. Process discovery and cloud query failures remain UNKNOWN rather than using older success.

The GitHub market_bot workflow was observed disabled_manually. A read-only dispatch was refused. Do not enable it as a connectivity fix: enabling also restores its scheduled production prediction writes, which require review of writer authority and safety first. Draft PR #125 repairs missing relay test dependencies; it is not deployed until merged through normal controls.

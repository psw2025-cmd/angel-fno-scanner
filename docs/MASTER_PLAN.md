# Master reliability execution plan — 2026-10-10

## Success
C1 encoding completes without RETRY_PENDING; C2 independent AGY review finishes under 180 seconds; C3 CI-reviewed change merged to main; C4 no proven orphan processes; C5 append-only cycle ledger and dashboard; C6 actual Windows file-lock injection passes; C7 full pytest passes; C8 --verify --json-only exits 0 with PYTHONIOENCODING cleared. Each requires separate local and remote evidence; remote status cannot be inferred from local tests.

## Failure decision tree
| Criterion | Probe | Narrow fix | Architecture / external fallback |
|---|---|---|---|
| C1 | supervisor state + git worktree list + exact stderr | bounded cleanup and retry with immutable evidence | quarantine only failed worktree; keep other tasks running |
| C2 | minimal noninteractive AGY call + process tree + auth status | reduce prompt, bound timeout, isolate review | independent Codex review with explicit reviewer identity; do not mislabel as AGY |
| C3 | branch SHA + CI checks + PR review | fix failed checks on feature branch | do not merge without required CI and review |
| C4 | owner PID + parent tree + creation time + worktree | reap only owned expired descendants | retain unknown processes and quarantine |
| C5 | ledger JSONL parse + unique cycle IDs | atomic append + fsync | reconstruct from immutable run IDs |
| C6 | hold file open and attempt worktree cleanup | bounded backoff + incident log | preserve workspace and retry after release |
| C7 | pytest from repository root | fix deterministic failures | isolate external tests and label accurately |
| C8 | CLI stdout, exit, API quota | batch and backoff Sheets reads | read-only cached evidence explicitly marked stale; do not fake live pass |

## Sequencing and controls
Read handoff and state first; do not run concurrent supervisors. Prove cause before adding modules. Protect LIVE trading and secrets. Each patch: syntax parse, regression, full local tests, feature branch, CI, independent review, then merge. No force pushes or deleting unknown processes. Preserve unresolved evidence. Reconcile main, Sheets, BigQuery and dashboard separately after authorized merge.

## Pre-emptive mitigations
Rate limiter: bounded bursts + observability. Cache: TTL, provenance and bypass. DLQ: max size alert and idempotent replay. Circuit breaker: half-open single probe and jitter. Metrics: nonblocking writes. ETL: quarantine rejects with reasons. No module is wired without caller tests.

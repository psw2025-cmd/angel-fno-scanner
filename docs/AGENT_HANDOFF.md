# Agent Handoff — Current State

**Last updated:** 2026-10-05 by agy CLI (Documentation & Sync Agent)  
**Repository state:** clean, in sync / tracking origin/main  
**HEAD commit:** `a69d182` "docs(audit): complete audit of existing repository documentation"  

## How To Verify Current State

Run: `python tools/verify_all.py`

Expected output:
- 154 tests passed
- 10 readiness gates PASS
- 1 gate NOT_PROVEN (runtime_provenance — closes on next market_bot run)
- 1 gate UNKNOWN (exact_sha_ci — closes when PR Tests runs against HEAD)
- All four BigQuery run_id columns are STRING

## Open Defects

See `docs/DEFECT_REGISTER.md` for the authoritative list. Summary:

| ID | Severity | Description | Owner |
|---|---|---|---|
| D-01 | HIGH | GATE-06 in Google Sheet checks wrong column; threshold relaxed to >=200 instead of fixed | Open (Product/Sheet) |
| D-05 | HIGH | PUBLICATION_STATUS shows FAILED_PARTIAL with blank digests | Open (Pipeline) |
| D-06 | HIGH | PREMARKET_VS_ACTUAL: 50% direction accuracy on 6 symbols | Open (Model Review) |
| D-07 | LOW | TOMORROW_EXPLOSIVE_WATCH and PREMARKET_VS_ACTUAL are 6 days stale | Open (Scheduler) |
| D-08 | MEDIUM | CE_PE_RANK column C always empty; GATE-06 formula references it anyway | Open (Schema) |

## Recently Closed Defects

| ID | Closed by | Date |
|---|---|---|
| D-02 | `eaccdaf` | 2026-10-05 |
| D-03 | `e1a68c0` | 2026-10-05 |
| D-04 | `e1a68c0` | 2026-10-05 |

## Pending Scheduled Events

- `runtime_provenance` closes on next successful market_bot run
- `exact_sha_ci` closes on next PR Tests workflow against current HEAD

## Protected Files — Read Before Editing

- `writer_guard.py` — single-writer contract
- `publication.py` — digest and lineage
- `universe_contract.py` — 219-symbol freeze
- All files in `tests/`

## How To Start Work

1. Read this file
2. Read `docs/AGENT_CONTRACT.md`
3. Run `python tools/verify_all.py`
4. If verification fails, stop and report
5. Pick a defect from `docs/DEFECT_REGISTER.md`

## Where Full History Lives

- `docs/CHANGELOG.md` — every commit, reverse chronological
- `docs/DEFECT_REGISTER.md` — every defect, all statuses
- `audit/` — forensic snapshots and evidence folders

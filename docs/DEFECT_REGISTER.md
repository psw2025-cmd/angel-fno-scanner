# Defect Register

Every defect ever found. Status tracked. Never delete rows.

| ID | Found | Description | Severity | Status | Closed by | Notes |
|---|---|---|---|---|---|---|
| D-01 | 2026-10-05 | GATE-06 in Google Sheet checks wrong column; threshold relaxed to >=200 instead of fixed | HIGH | OPEN | — | See `docs/decisions/D-01.md` |
| D-02 | 2026-10-05 | Four BigQuery writers used autodetect=True; run_id inferred as INT64 | HIGH | CLOSED | eaccdaf | Pinned schemas on all 5 BQ writers |
| D-03 | 2026-10-05 | scanner.py missing literal EXPECTED_FNO_UNIVERSE_COUNT | MEDIUM | CLOSED | e1a68c0 | Literal added for AST parser |
| D-04 | 2026-10-05 | infra_readiness AST parser used wrong node accessor | MEDIUM | CLOSED | e1a68c0 | Node accessor repaired |
| D-05 | 2026-10-05 | PUBLICATION_STATUS shows FAILED_PARTIAL with blank digests | HIGH | OPEN | — | See `docs/decisions/D-05.md` |
| D-06 | 2026-10-05 | PREMARKET_VS_ACTUAL: 50% direction accuracy on 6 symbols | HIGH | OPEN | — | See `docs/decisions/D-06.md` |
| D-07 | 2026-10-05 | TOMORROW_EXPLOSIVE_WATCH and PREMARKET_VS_ACTUAL are 6 days stale | LOW | OPEN | — | See `docs/decisions/D-07.md` |
| D-08 | 2026-10-05 | CE_PE_RANK column C always empty; GATE-06 formula references it anyway | MEDIUM | OPEN | — | See `docs/decisions/D-08.md` |

## Status definitions
- **OPEN**: defect confirmed, no fix in progress
- **IN_PROGRESS**: agent is working on a fix
- **CLOSED**: fix committed and verified by `verify_all.py`
- **REOPENED**: fix was committed but a later verification failed
- **WONTFIX**: acknowledged, will not be fixed; reason documented
- **DUPLICATE**: same as another defect; see the primary ID

## Notes per defect

### D-01 — GATE-06 wrong column
The formula `=COUNTA(CE_PE_RANK!C3:C218)=216` checks column C which is always blank in the data.
The correct check is `=COUNTA(CE_PE_RANK!A5:A204)=200`. See `docs/decisions/D-01.md` and `docs/formula-checks-contract.md`.

### D-02 — BigQuery run_id INT64 inference
`LoadJobConfig` in `angel_prediction_engine.py` used `autodetect=True`, causing BigQuery to infer numeric string run IDs as `INT64`.
Fixed in commit `eaccdaf`: pinned `schema` and set `autodetect=False` across all five writers.

### D-03 — scanner.py missing universe literal
The AST scanner in `scripts/infra_readiness.py` required a top-level assignment `EXPECTED_FNO_UNIVERSE_COUNT = 219`.
Fixed in commit `e1a68c0`.

### D-04 — infra_readiness AST parser accessor
The AST parser accessed `.value.args[0].args[1]` on `ast.Constant`. Replaced with `ast.literal_eval(node.value)`.
Fixed in commit `e1a68c0`.

### D-05 — PUBLICATION_STATUS FAILED_PARTIAL
Latest row: `FAILED_PARTIAL` with blank SHA256 digests.
Investigation needed in `publication.py` and the writer path. See `docs/decisions/D-05.md`.

### D-06 — PREMARKET_VS_ACTUAL 50% accuracy
6 symbols, 3 correct, 3 wrong. Mean gap error 2.54 percentage points.
Model review needed, not a code fix. See `docs/decisions/D-06.md`.

### D-07 — Stale tabs
`TOMORROW_EXPLOSIVE_WATCH` header says "FOR 29-SEP-2026".
`PREMARKET_VS_ACTUAL` header says "28-SEP-2026".
Both need regeneration or renaming. See `docs/decisions/D-07.md`.

### D-08 — CE_PE_RANK column C empty
Every data row in `CE_PE_RANK` has an empty column C.
GATE-06 formula references `CE_PE_RANK!C3:C218` which is therefore always 0 or blank.
Either the formula is wrong or the data schema is wrong. See `docs/decisions/D-08.md`.

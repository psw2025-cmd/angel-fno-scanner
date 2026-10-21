# IMPLEMENTATION_REPORT: CDX-01 to CDX-06

- **Date:** 2026-10-15 (IST)
- **Repository:** `psw2025-cmd/angel-fno-scanner`, working tree `C:\AngelFNO_Workstation\repos\angel-fno-scanner`
- **Branch / HEAD:** `docs/trigger-reference` @ `0e80b18b79f069df1c9813b1e210ef5472ee1a29` (changes are uncommitted)
- **Scope:** CDX-01 to CDX-06 only. CDX-07 to CDX-12 were not touched. No new audit and no regenerated findings.
- **Safety:** PAPER / ANALYZER = ON, LIVE ORDER AUTHORITY = OFF. No broker order API was added or called. No push, merge, deploy or secret change was made.
- **Status vocabulary (AGENTS.md section 8):** every item below is `IMPLEMENTED_NOT_DEPLOYED`. None is `RESOLVED_TWO_PARTY`; each still needs a peer check and runtime proof.

## Results

| Task | Status | Tests added | Full suite after |
|---|---|---|---|
| Baseline (before changes) | n/a | n/a | 287 passed |
| CDX-01 BigQuery timeouts | IMPLEMENTED_NOT_DEPLOYED | 5 | 292 passed |
| CDX-02 Schema guard (PR #97) | IMPLEMENTED_NOT_DEPLOYED (PR itself not merged, see below) | 11 | 303 passed |
| CDX-03 Pin requirements | IMPLEMENTED_NOT_DEPLOYED | 0 | 303 passed |
| CDX-04 Remove `.git` from image | IMPLEMENTED_NOT_DEPLOYED (image build not run) | 7 | n/a (targeted: 17 passed) |
| CDX-05 Timezone-aware `now_ist()` | IMPLEMENTED_NOT_DEPLOYED | 11 | n/a (targeted: 43 passed) |
| CDX-06 Breaker and limiter in quote loop | IMPLEMENTED_NOT_DEPLOYED | 7 | **328 passed** |

Final gates: full suite 328 passed. `test_runtime_safety`, `test_single_writer_architecture`, `test_cycle_provenance_and_lease` and `test_encoding_gate` gave 29 passed. `py_compile` is clean.

---

## CDX-01: BigQuery `job.result()` timeouts

- **Impacted files:** `angel_prediction_engine.py`, `tests/test_bq_timeout.py` (new), `tests/test_publication_integrity.py` (test fake).
- **Root cause:** `job.result()` had no `timeout`. A hung BigQuery API blocks the run until an outer GitHub Actions or Cloud Run limit kills it, with no failure telemetry and no rows saved.
- **Change:**
  - Added `DEFAULT_BQ_TIMEOUT_SECONDS` (env `BQ_LOAD_TIMEOUT_SECONDS`, default 60) and a helper `bq_job_result(job, table_name, rows)`.
  - On timeout it cancels the job (best effort) and buffers the rows with `scanner.write_local_backup_buffer`. It then raises `RuntimeError`.
  - On `GoogleAPICallError` it buffers the rows and re-raises.
  - If the buffer write itself fails, that is logged and does not mask the original error.
  - All 5 BigQuery load-job waits now use it: `next_day_gap_predictions` (2), `option_predictions_live`, `market_news_sentiment`, `prediction_calibration_log`.
- **Deviations from the backlog:**
  - The backlog lists 3 call sites. I covered all 5, because its rule 3 says "wrap all `.result()` calls".
  - Added a best-effort `job.cancel()` on timeout, so a late server-side commit does not duplicate rows that were just buffered.
  - `fut.result()` at line 651 is a `ThreadPoolExecutor` future, not BigQuery, so it was left alone.
- **Regression found and fixed during validation:** the fake load job in `tests/test_publication_integrity.py` defined `result()` with no arguments. This caused 5 failures. It now accepts `timeout=None`, matching the real BigQuery signature.

## CDX-02: Live schema guard (PR #97)

- **Impacted files:** `tools/live_schema_guard.py` (untracked locally), `angel_prediction_engine.py` (`sync_to_bigquery`), `tests/test_schema_guard_int64.py` (new).
- **Observation on the backlog text vs PR #97:**
  - PR #97 ([link](https://github.com/psw2025-cmd/angel-fno-scanner/pull/97), open, mergeable, head `6aa8172`) actually does two things.
    - It canonicalises `FLOAT`/`FLOAT64` and `INTEGER`/`INT64` in the `WRITE_TRUNCATE` retype check, which fixes false refusals on `option_predictions_live`.
    - It removes `COPY .git .git` from `Dockerfile.cloudrun`.
  - The backlog describes a different fix: float to INT64 coercion for `market_news_sentiment`, via `sanitize_bq_row` and `enforce_live_schema_types`. Neither function existed.
  - I implemented both: the PR's `_canon` behaviour, plus the coercion the backlog asks for.
- **Change:**
  - `_canon()` is applied on both sides of the retype comparison, with the same behaviour as the PR. Real retypes (for example FLOAT64 to STRING) are still refused.
  - New `sanitize_bq_row(table, row)` is driven by `schemas/<table>.json`, so it cannot drift from the contract.
    - Floats for INT64 columns become `int(round(v))`.
    - `None` and `bool` are left alone.
    - The input row is not mutated.
  - It is applied to `option_predictions_live`, `market_news_sentiment` and `prediction_calibration_log` inside `sync_to_bigquery()`.
- **Deviations from the backlog:**
  - The backlog's hard-coded field list (`article_count`, `bullish_count`, ...) does not exist in the real schema. The real INT64 news columns are `source_count` and `severity_level`, so coercion is schema-driven.
  - The backlog sets unconvertible values to `0`. That silently corrupts data, which conflicts with fail-closed (AGENTS.md section 13). It raises `SchemaGuardError` instead.
  - The backlog's validation one-liner uses `cycle_number` against `market_news_sentiment`, which is not a column there. I ran the equivalent check against `prediction_calibration_log`, which does have `cycle_number` as INT64.
- **Merge not performed (needs your decision):**
  - A local `git merge` would conflict with the untracked `tools/live_schema_guard.py` and mix about 46 unrelated files into this branch.
  - Merging on GitHub changes `main` and the deployment pipeline. AGENTS.md section 26 requires project governance for that.
  - Applying the PR's change locally gives the same code effect.
  - After you merge PR #97, expect a trivial conflict in `tools/live_schema_guard.py` (the `_canon` helper has moved to module level) and in `Dockerfile.cloudrun`.

## CDX-03: Pin `requirements.txt`

- **Impacted file:** `requirements.txt`.
- **Root cause:** only `smartapi-python` was pinned, so every CI run or image build could pull untested major releases.
- **Change:** all 10 packages are pinned to the exact versions the 287-test baseline passed against: `websocket-client==1.9.2`, `pycryptodome==3.23.0`, `pyotp==2.10.0`, `gspread==6.2.1`, `google-cloud-bigquery==3.45.2`, `pytz==2026.4`, `tzdata==2026.4`, `requests==2.34.2`, `logzero==1.7.0`, `smartapi-python==1.5.5`.
- **Deviation:** the backlog's pins (for example `google-cloud-bigquery==3.25.0`, `gspread==6.1.2`, `pycryptodome==3.20.0`) are older than anything tested here. Its text claims they are "verified", but they were never run against this suite, so I did not use them.
- **Validation:** `pip install --dry-run` resolves, `pip check` reports no broken requirements, and all packages import.
- **Residual risk:** transitive dependencies (for example `google-api-core`, `google-auth`) are still not locked. A hash-locked file would be a separate task.

## CDX-04: Remove `.git` from the Cloud Run image

- **Impacted files:** `Dockerfile.cloudrun`, `.dockerignore`, `Dockerfile` (see below), `tests/test_container_provenance.py` (new).
- **Root cause:** `COPY .git .git` shipped full repository history and author metadata into the production image. The image already receives commit identity through `ARG SOURCE_COMMIT`.
- **Change:**
  - Removed `COPY .git .git`.
  - Added `ENV GIT_SHA=$SOURCE_COMMIT` after the existing `ARG`. `/app/SOURCE_COMMIT` was already written.
  - Added `.git` and `.github` to `.dockerignore`.
- **`tools/cycle_provenance.py` left unchanged.** `resolve_git_sha()` already checks `GITHUB_SHA`, `GIT_SHA`, `SOURCE_COMMIT`, then `/app/SOURCE_COMMIT`. It deliberately never runs `git rev-parse` and never invents a SHA. Adding a git fallback would weaken that fail-closed design. A placeholder build arg (`unknown`) still fails closed.
- **Extra edit (side effect of this task):** the plain, untracked `Dockerfile` also had `COPY .git .git`. With `.git` now in the shared `.dockerignore`, that build would fail, so I removed that single line. Nothing else in it was changed. No build config references it.
- **NOT VERIFIED:** I did not run `docker build`. File-level tests only.

## CDX-05: Timezone-aware `now_ist()`

- **Impacted files:** `scanner.py`, `tests/test_now_ist_aware.py` (new).
- **Root cause:** `now_ist()` stripped tzinfo, so naive and aware datetimes met across modules.
- **Change:**
  - `now_ist()` returns an aware IST datetime.
  - New `parse_sheet_ist()` parses sheet timestamps as IST-aware.
  - `heartbeat_age_seconds(book, now=None)` accepts a naive or aware `now`, uses the shared parser, and clamps at 0.0.
- **Backlog gap fixed:** `run_angel_loop` computes `now - last_time` where `last_time` was a naive `strptime` value inside `except Exception: pass`. After making `now` aware this would have raised `TypeError`, been swallowed, and silently disabled outage detection in the HEARTBEAT sheet. It now uses `parse_sheet_ist`.
- **No change needed:** `writer_guard.py` and `angel_prediction_engine.get_ist_time()` were already aware. `market_is_open`, `local_market_time`, `paper_log` and `gainers.year_fraction` already handle both. I confirmed this by reading each of them.
- **Left as is on purpose:** `parse_news_timestamp_ist` in the engine deliberately emits naive IST ISO strings for stored news timestamps. Changing it would change a data format, which is outside CDX-05.

## CDX-06: Circuit breaker and rate limiter in `fetch_chunked`

- **Impacted files:** `scanner.py`, `tests/test_fetch_chunked_resilience.py` (new). `circuit_breaker.py` and `rate_limiter.py` were not modified.
- **Root cause:** both utilities existed and were unit tested, but the live quote loop only used `time.sleep(0.35)`. Repeated broker errors never tripped anything.
- **Observation:** the backlog snippet uses an API that does not exist. The real classes are `CircuitBreaker(threshold, cooldown)` with `allow()`, `success()` and `failure()`, and `RateLimiter(rate, capacity)` where `acquire()` is non-blocking and returns the seconds to wait. `CircuitBreaker(failure_threshold=..., name=...)` and `.call()` belong to the different `tools/recovery.py`.
- **Change:**
  - Added module-level `smartapi_breaker = CircuitBreaker(threshold=4, cooldown=45.0)` and `smartapi_limiter = RateLimiter(rate=3, capacity=1)`. That is 3 calls per second with no burst, never looser than the old 0.35s pacing.
  - A `_throttle_smartapi()` helper sleeps the wait that `acquire()` returns, before every API attempt including retries.
  - `success()` or `failure()` is recorded for each attempt. Retry and backoff logic is unchanged.
  - When the breaker is open, the remaining chunks are skipped with no API calls. They are counted in `failures`, and a warning is logged.
  - Callers already treat "no quotes and failures > 0" as an API failure ("Existing sheets were left unchanged", sleep 30s, re-login after 3 in a row), so the sheets stay untouched without any caller change.
  - The fixed `time.sleep(0.35)` was removed, because the limiter replaces it.
- **Behaviour to watch at runtime:** an open breaker lasts 45s but the loop sleeps 30s, so one more cycle may be skipped before the half-open probe. A persistent data-quality error (for example stale exchange timestamps with `ANGEL_REQUIRE_EXCHANGE_TIME=1`) also counts as a failure and can open the breaker. That fails closed, but it is new behaviour.

---

## Files changed (this run)

Modified:
- `angel_prediction_engine.py`
- `scanner.py`
- `requirements.txt`
- `Dockerfile.cloudrun`
- `.dockerignore`
- `tests/test_publication_integrity.py`

Untracked, edited or created:
- `Dockerfile`
- `tools/live_schema_guard.py`
- `tests/test_bq_timeout.py`
- `tests/test_schema_guard_int64.py`
- `tests/test_container_provenance.py`
- `tests/test_now_ist_aware.py`
- `tests/test_fetch_chunked_resilience.py`

Some of these files already carried uncommitted changes before this run, so `git diff HEAD` also shows that earlier work.

## Rollback

The backlog's `git checkout HEAD -- <file>` rollbacks **must not be used** here. They would erase uncommitted work that predates this run (`angel_prediction_engine.py`, `scanner.py`, `Dockerfile.cloudrun`, `tools/live_schema_guard.py`). A pre-change snapshot is at `C:\temp\AngelFNO\impl_backup_20261015\` (`angel_prediction_engine.py`, `scanner.py`, `requirements.txt`, `Dockerfile.cloudrun`, `.dockerignore`, `writer_guard.py`, `tools/cycle_provenance.py`, `tools/live_schema_guard.py`). Restore from there if needed. Two files are not in the snapshot: `Dockerfile` (only the `COPY .git .git` line was removed) and `tests/test_publication_integrity.py` (only `result()` became `result(timeout=None)`).

## NOT VERIFIED / open items

1. **Runtime proof:** nothing was deployed and no BigQuery, Sheets or broker call was made. All proof is local pytest, with mocks and fakes. BigQuery timeout behaviour, the live breaker and limiter against SmartAPI, and the INT64 coercion against real load jobs still need an active-session check.
2. **Docker image build** (CDX-04) was not run.
3. **PR #97 is still open.** Merging it is your call (see CDX-02).
4. **Peer verification** (AGY / ChatGPT lane) and the Issue #3 cross-agent packet were not produced. The backlog's `tools/agy_cross_agent_packet.ps1` step posts to a shared bus and was outside the six-task scope.
5. **Observations outside scope, not acted on:**
   - `scanner.py` still holds a hard-coded `219` in places and the duplicated `EXPECTED_FNO_UNIVERSE_COUNT` literal (CDX-08).
   - The scanner still has mojibake emoji strings (`ðŸŸ¢`) in the heartbeat status text.
   - The plain `Dockerfile` has no `SOURCE_COMMIT` handling.

## Stopped after CDX-06

CDX-07 to CDX-12 are untouched.

# Long-horizon autonomy: engineering design and limits

**Status: architecture and fail-closed guard foundation, not 100-year certified.** No software can guarantee 100 years without failure or guarantee predictive accuracy.

## Authority and safety
GitHub main is code authority. Angel One FULL exchange timestamps are the primary market quote provenance. Sheets, BigQuery and Git snapshots are independent publication sinks. PAPER/ANALYZE only; no automated real-money order enablement. No self-modifying production code without tests, protected PR, reproducible CI and explicit promotion policy.

## Historical failure taxonomy
Investigate every failure with immutable run ID, SHA, source exchange time, writer identity, sink acknowledgments, and root-cause tag. Historical clusters are not periodicity evidence without dated run denominators. Known classes: 216/219 universe drift, stale formula PASS, missing exchange time, partial publication, CI push retry exhaustion, runtime timeouts and sink schema drift. PR #13 addressed manifest and single-writer controls; PR #31 live integrity; PR #34 alert/EOD fixes; PR #38 exchange provenance and snapshot staging. Validate PR descriptions against code and actual incident logs.

## Single writer and transactional publication
Workflow concurrency group alone does not lock other workflows or external writers. Use an external lease with fencing token and expiry, writer ACLs, and unique (session, cycle_id, symbol) keys. Stage immutable cycle bundles, compute SHA-256 manifest, publish a single version pointer only after every sink acknowledges the same manifest. Current multi-file replace/rollback is **not crash-atomic**: SIGKILL can leave a mixed bundle. Recover by replaying the last committed manifest; never delete evidence. Git pushes need compare-and-swap and bounded retry. Sheets is not a transactional database; reconcile after writes.

## Preflight
Check exchange calendar/holiday and timezone, Angel session, clock skew, token schema and uniqueness, complete dynamic exchange universe (versioned manifest, not blindly fixed 219), timestamp parsing including broker format and leap-second policy, coverage, and max age appropriate to session. Abort on missing or stale data; distinguish closed market from broken market. Circuit breaker with exponential backoff/jitter and finite attempts; DLQ contains redacted failure envelopes, never credentials.

## Postflight
Read back real Sheet rows and BigQuery rows with exact cycle ID, version, count, checksum, dedupe key and commit marker. Account for BQ streaming visibility with bounded eventual-consistency wait; never report success from write acknowledgment alone. Quarantine mismatches, alert, retry idempotently, and preserve the previous verified version.

## Learning without uncontrolled trading
Append append-only, redacted run metrics: coverage, API latency, oldest tick age, SDK version, market calendar version, source divergence, sink hash, incident class. Compare Angel vs licensed NSE/BSE sources only when symbol/contract, timestamp and market segment are genuinely comparable. Use rolling calibration, walk-forward evaluation, drift detection, holdout data, and risk gates. A proposed batch-size change after three slow runs is a candidate experiment, not an automatic unsafe production change.

## Evolution and recovery
Pin dependencies and generate SBOM; automated dependency PRs run integration and chaos tests. Version schemas with additive migrations, backward compatibility and feature flags. OpenTelemetry traces link API fetch to sink acknowledgments via trace_id; redact tokens and PII. Backup and regularly restore-test config, manifests and metadata. Exercise process termination, partial sink writes, API timeouts, quota exhaustion, duplicates, holidays and token-universe changes. Track RTO/RPO, coverage SLO, reconciliation SLO, MTTR and false-positive rates.

## Verification boundary
The initial guard deliberately **fails postflight** until authenticated external Sheet and BigQuery readback is implemented. This prevents claiming unverified production success. A real 219/219 read-only Angel probe proves exchange coverage, not sink parity. Do not make a blocking production postflight required until the real readback adapter and safe recovery path pass staging.

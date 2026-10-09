# Learning loop

Collect run-level metrics as append-only JSONL with run_id, commit SHA, UTC start/end, exchange timestamp, coverage, API latency, age, API/SDK version, calendar version, sink reconciliation hash, and error class. Do not synthesize historical entries. Require at least ten actual, independently retrieved runs before presenting a ten-run analysis; missing logs remain UNKNOWN.

Classify failures, calculate rolling SLOs, compare like-for-like broker/exchange observations, propose tuning on a separate branch, run chaos and walk-forward validation, then promote via protected CI. Three consecutive runs above 10 seconds may trigger a *proposal* to reduce batch size. A circuit breaker and dead-letter queue are operational recovery, not predictive model learning. Never auto-enable live trading.

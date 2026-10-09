#!/usr/bin/env python3
"""
tools/test_recovery.py
100-Year Autonomy Architecture — Fault Injection Test Suite for Recovery Engine
Validates:
1. Exponential backoff retry execution
2. Dead Letter Queue (DLQ) persistent recording with SHA-256 payload integrity
3. Circuit breaker trip to OPEN state on 3 consecutive failures
4. Circuit breaker block verification
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.recovery import (
    CircuitBreaker,
    CircuitBreakerOpenException,
    DeadLetterQueue,
    retry_with_backoff,
)


def test_transient_failure_recovery():
    """Inject 2 transient failures; function must succeed on 3rd attempt."""
    attempts = 0

    @retry_with_backoff(max_retries=3, base_delay=0.01, backoff_factor=1.5)
    def flaky_service():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionResetError(f"Simulated network drop on attempt {attempts}")
        return "SUCCESS_ON_ATTEMPT_3"

    result = flaky_service()
    assert result == "SUCCESS_ON_ATTEMPT_3", f"Expected success, got {result}"
    assert attempts == 3, f"Expected exactly 3 attempts, got {attempts}"
    print("[PASS] test_transient_failure_recovery: Recovered after 2 transient failures")


def test_permanent_failure_and_dlq():
    """Inject permanent failure; must exhaust 3 retries and record into DLQ."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        temp_dlq_path = Path(tf.name)

    try:
        dlq = DeadLetterQueue(path=temp_dlq_path)
        test_payload = {"symbol": "RELIANCE", "strike": 3000, "token": 99999}
        attempts = 0

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            backoff_factor=1.5,
            dlq=dlq,
            run_id="test_run_fail_999"
        )
        def broken_sink():
            nonlocal attempts
            attempts += 1
            raise TimeoutError("Simulated upstream broker timeout")

        try:
            broken_sink()
            assert False, "Expected TimeoutError was not raised"
        except TimeoutError:
            pass

        assert attempts == 3, f"Expected 3 retry attempts, got {attempts}"

        records = dlq.read_all()
        assert len(records) == 1, f"Expected 1 record in DLQ, got {len(records)}"
        rec = records[0]
        assert rec["run_id"] == "test_run_fail_999"
        assert rec["error_type"] == "TimeoutError"
        assert rec["retry_count"] == 3
        assert len(rec["payload_hash"]) == 64  # Valid SHA-256 hex string

        print("[PASS] test_permanent_failure_and_dlq: Permanent failure captured into DLQ with SHA-256 hash")
    finally:
        if temp_dlq_path.exists():
            temp_dlq_path.unlink()


def test_circuit_breaker_trip_and_block():
    """Inject 3 consecutive failures; breaker must trip OPEN and reject 4th call without execution."""
    cb = CircuitBreaker(failure_threshold=3, reset_timeout_seconds=5.0, name="test_breaker")
    assert cb.state == "CLOSED"
    assert cb.can_execute() is True

    # 1st failure
    cb.record_failure()
    assert cb.state == "CLOSED"

    # 2nd failure
    cb.record_failure()
    assert cb.state == "CLOSED"

    # 3rd failure -> trips OPEN
    cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.can_execute() is False

    # 4th call must be blocked immediately
    blocked = False
    try:
        cb.check()
    except CircuitBreakerOpenException:
        blocked = True
    assert blocked is True, "Circuit breaker failed to block call while OPEN"

    print("[PASS] test_circuit_breaker_trip_and_block: Breaker correctly tripped to OPEN after 3 failures")


def main():
    print("=" * 70)
    print("RUNNING RECOVERY ENGINE FAULT-INJECTION TESTS")
    print("=" * 70)
    test_transient_failure_recovery()
    test_permanent_failure_and_dlq()
    test_circuit_breaker_trip_and_block()
    print("=" * 70)
    print("ALL 3 RECOVERY ENGINE TESTS PASSED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
tools/recovery.py
100-Year Autonomy Architecture — Fault-Tolerant Recovery & Resilience Engine
1. Exponential backoff retry handler (max 3 retries)
2. Circuit breaker pattern (opens for 15 minutes after 3 consecutive failures)
3. Dead Letter Queue (DLQ) persisted to data/dead_letter_queue.jsonl with cryptographic payload hash
"""

import datetime
import functools
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DLQ_PATH = DATA_DIR / "dead_letter_queue.jsonl"

logger = logging.getLogger("RecoveryEngine")


class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""
    pass


class CircuitBreaker:
    """
    Circuit Breaker pattern.
    Transitions:
    - CLOSED -> OPEN after failure_threshold consecutive failures
    - OPEN -> HALF_OPEN after reset_timeout_seconds (default 15 minutes = 900s)
    - HALF_OPEN -> CLOSED on successful trial
    - HALF_OPEN -> OPEN on failure
    """
    def __init__(self, failure_threshold: int = 3, reset_timeout_seconds: float = 900.0, name: str = "default"):
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self.name = name
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # "CLOSED", "OPEN", "HALF_OPEN"

    def record_success(self):
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker '{self.name}' tripped to OPEN (15min timeout)")

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if self.last_failure_time and (time.time() - self.last_failure_time >= self.reset_timeout_seconds):
                self.state = "HALF_OPEN"
                logger.info(f"Circuit breaker '{self.name}' entered HALF_OPEN state for trial")
                return True
            return False
        if self.state == "HALF_OPEN":
            return True
        return False

    def check(self):
        if not self.can_execute():
            remaining = self.reset_timeout_seconds - (time.time() - (self.last_failure_time or 0))
            raise CircuitBreakerOpenException(
                f"Circuit breaker '{self.name}' is OPEN. Retry blocked for {max(0, remaining):.1f}s"
            )


class DeadLetterQueue:
    """
    Append-only Dead Letter Queue.
    Logs failed payloads with run_id, exception details, retry count, and SHA-256 payload hash.
    """
    def __init__(self, path: Path = DLQ_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def compute_hash(self, payload: Any) -> str:
        if payload is None:
            return "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"  # sha256("")
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def record_failure(
        self,
        run_id: str,
        error: Exception,
        payload: Any = None,
        retry_count: int = 3,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        payload_hash = self.compute_hash(payload)
        record = {
            "run_id": str(run_id),
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "retry_count": retry_count,
            "payload_hash": payload_hash,
            "payload_preview": str(payload)[:200] if payload else None,
            "metadata": metadata or {}
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        logger.info(f"[DLQ] Appended failure record for run {run_id} (hash {payload_hash[:8]})")
        return record

    def read_all(self):
        if not self.path.exists():
            return []
        records = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass
        return records


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 0.5,
    backoff_factor: float = 2.0,
    circuit_breaker: Optional[CircuitBreaker] = None,
    dlq: Optional[DeadLetterQueue] = None,
    run_id: str = "recovery_call"
):
    """
    Decorator executing a callable with exponential backoff and optional circuit breaker + DLQ.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if circuit_breaker:
                circuit_breaker.check()

            last_exc = None
            delay = base_delay
            for attempt in range(1, max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if circuit_breaker:
                        circuit_breaker.record_success()
                    return result
                except Exception as exc:
                    last_exc = exc
                    logger.warning(f"Attempt {attempt}/{max_retries} failed for {func.__name__}: {exc}")
                    if attempt < max_retries:
                        time.sleep(delay)
                        delay *= backoff_factor

            # All retries exhausted
            if circuit_breaker:
                circuit_breaker.record_failure()
            if dlq:
                dlq.record_failure(
                    run_id=run_id,
                    error=last_exc,
                    payload={"args": [str(a)[:50] for a in args], "kwargs": {k: str(v)[:50] for k, v in kwargs.items()}},
                    retry_count=max_retries
                )
            raise last_exc
        return wrapper
    return decorator


if __name__ == "__main__":
    print(f"[RECOVERY] Engine initialized. DLQ at {DLQ_PATH}")

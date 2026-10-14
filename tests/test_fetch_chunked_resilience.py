"""CDX-06 regression: fetch_chunked is rate limited and guarded by a circuit breaker."""
import pytest

import scanner
from circuit_breaker import CircuitBreaker
from rate_limiter import RateLimiter


class Clock:
    def __init__(self):
        self.t = 1000.0
        self.sleeps = []

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds


class FakeApi:
    def __init__(self, responder):
        self.responder = responder
        self.calls = []

    def getMarketData(self, mode, payload):
        self.calls.append(payload["NFO"])
        return self.responder(len(self.calls), payload["NFO"])


def ok(_n, chunk):
    return {"status": True, "data": {"fetched": [{"symbolToken": t, "ltp": 1.0} for t in chunk]}}


def bad(_n, _chunk):
    return {"status": False}


@pytest.fixture
def env(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(scanner.time, "sleep", clock.sleep)
    monkeypatch.setattr(scanner, "smartapi_breaker", CircuitBreaker(threshold=4, cooldown=45.0, clock=clock))
    monkeypatch.setattr(scanner, "smartapi_limiter", RateLimiter(rate=3, capacity=1, clock=clock))
    monkeypatch.delenv("ANGEL_REQUIRE_EXCHANGE_TIME", raising=False)
    return clock


def test_module_defaults_match_backlog():
    assert isinstance(scanner.smartapi_breaker, CircuitBreaker)
    assert scanner.smartapi_breaker.threshold == 4 and scanner.smartapi_breaker.cooldown == 45.0
    assert isinstance(scanner.smartapi_limiter, RateLimiter)
    assert scanner.smartapi_limiter.rate == 3 and scanner.smartapi_limiter.capacity == 1


def test_healthy_run_returns_all_quotes_and_throttles(env):
    tokens = [str(i) for i in range(135)]  # 3 chunks of 45
    api = FakeApi(ok)
    quotes, failures = scanner.fetch_chunked(api, tokens)
    assert failures == 0 and len(quotes) == 135 and len(api.calls) == 3
    # no burst: calls 2 and 3 each had to wait ~1/3 s
    assert len(env.sleeps) == 2 and all(abs(s - 1 / 3) < 1e-6 for s in env.sleeps)


def test_transient_failure_recovers_and_resets_breaker(env):
    api = FakeApi(lambda n, chunk: bad(n, chunk) if n == 1 else ok(n, chunk))
    quotes, failures = scanner.fetch_chunked(api, ["1", "2"])
    assert failures == 0 and set(quotes) == {"1", "2"}
    assert scanner.smartapi_breaker.failures == 0 and scanner.smartapi_breaker.opened_at is None


def test_breaker_opens_and_remaining_chunks_skipped_without_api_calls(env):
    tokens = [str(i) for i in range(45 * 5)]  # 5 chunks
    api = FakeApi(bad)
    quotes, failures = scanner.fetch_chunked(api, tokens)
    assert quotes == {}
    assert len(api.calls) == 4  # threshold reached on 4th failed call; nothing after
    assert scanner.smartapi_breaker.opened_at is not None
    assert failures == 5  # every chunk accounted for so the caller fails closed


def test_open_breaker_makes_zero_calls_until_cooldown_then_probes(env):
    api = FakeApi(bad)
    scanner.fetch_chunked(api, ["1"])  # trips the breaker
    api.calls.clear()
    quotes, failures = scanner.fetch_chunked(api, ["1", "2"])
    assert api.calls == [] and quotes == {} and failures == 1
    env.t += 46  # cooldown elapsed -> single probe allowed
    healthy = FakeApi(ok)
    quotes, failures = scanner.fetch_chunked(healthy, ["1"])
    assert failures == 0 and "1" in quotes
    assert scanner.smartapi_breaker.opened_at is None


def test_failed_probe_reopens_breaker(env):
    api = FakeApi(bad)
    scanner.fetch_chunked(api, ["1"])
    env.t += 46
    api.calls.clear()
    _, failures = scanner.fetch_chunked(api, ["1"])
    assert len(api.calls) == 1 and failures == 1  # one probe, no retry storm
    assert scanner.smartapi_breaker.allow() is False


def test_exceptions_from_api_are_counted_not_raised(env):
    def boom(_n, _c):
        raise ConnectionError("down")
    quotes, failures = scanner.fetch_chunked(FakeApi(boom), ["1"])
    assert quotes == {} and failures >= 1

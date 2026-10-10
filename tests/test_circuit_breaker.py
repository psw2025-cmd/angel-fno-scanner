from circuit_breaker import CircuitBreaker

def test_open_half_open_and_recover():
    now=[0]
    breaker=CircuitBreaker(threshold=2,cooldown=10,clock=lambda:now[0])
    breaker.failure()
    assert breaker.allow()
    breaker.failure()
    assert not breaker.allow()
    now[0]=10
    assert breaker.allow()
    assert not breaker.allow()
    breaker.success()
    assert breaker.allow()

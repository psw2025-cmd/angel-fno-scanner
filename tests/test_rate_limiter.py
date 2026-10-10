import pytest
from rate_limiter import RateLimiter

def test_burst_and_refill():
    clock=[0]
    limiter=RateLimiter(rate=2,capacity=2,clock=lambda:clock[0])
    assert limiter.acquire()==0
    assert limiter.acquire()==0
    assert limiter.acquire()==0.5
    clock[0]=0.5
    assert limiter.acquire()==0

def test_invalid_cost():
    limiter=RateLimiter(rate=1,capacity=1)
    with pytest.raises(ValueError):limiter.acquire(2)

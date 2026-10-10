import pytest
from cache import TTLCache

def test_ttl_and_lru():
    clock=[0]
    cache=TTLCache(ttl=5,maxsize=2,clock=lambda:clock[0])
    cache.put("a",1)
    cache.put("b",2)
    assert cache.get("a")==1
    cache.put("c",3)
    assert cache.get("b") is None
    clock[0]=5
    assert cache.get("a") is None

def test_invalid_cache():
    with pytest.raises(ValueError):TTLCache(ttl=0)

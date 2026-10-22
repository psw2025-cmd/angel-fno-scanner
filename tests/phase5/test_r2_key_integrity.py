"""Reject ambiguous evidence keys before any remote R2 operation."""
import sys
import types
import pytest
from src.phase5_engine.r2 import write_immutable

@pytest.mark.parametrize("key", [
    "predictions/", "predictions//a.json", "predictions/../metrics/a.json",
    "predictions/./a.json", "predictions/a.json/", "predictions/a\\\\b.json",
    "predictions/a\\nb.json", "unknown/a.json", "", None, 123,
])
def test_invalid_key_rejected_without_network(monkeypatch, key):
    for name in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "PHASE5_R2_BUCKET"):
        monkeypatch.setenv(name, "test")
    def forbidden_client(*args, **kwargs):
        raise AssertionError("Network client must not be created")
    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(client=forbidden_client))
    with pytest.raises(ValueError, match="Invalid evidence key"):
        write_immutable(key, {"test": True})

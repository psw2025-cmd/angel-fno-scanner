"""Offline negative, boundary and retry tests for broker FULL quote integrity."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.quote_batch_guard import QuoteBatchIntegrityError, require_complete_quote_chunk

ROOT = Path(__file__).resolve().parents[1]


def payload(*tokens, unfetched=None):
    return {"status": True, "data": {"fetched": [{"symbolToken": t} for t in tokens], "unfetched": unfetched or []}}


def reject(code, tokens, response):
    with pytest.raises(QuoteBatchIntegrityError) as exc:
        require_complete_quote_chunk(tokens, response)
    assert exc.value.code == code


def load_real_fetch_chunked(monkeypatch):
    tree = ast.parse((ROOT / "scanner.py").read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "fetch_chunked")
    namespace = {
        "os": os,
        "time": SimpleNamespace(sleep=lambda _delay: None),
        "QuoteBatchIntegrityError": QuoteBatchIntegrityError,
        "require_complete_quote_chunk": require_complete_quote_chunk,
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), "scanner.py", "exec"), namespace)
    monkeypatch.delenv("ANGEL_REQUIRE_EXCHANGE_TIME", raising=False)
    return namespace["fetch_chunked"]


class FakeApi:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def getMarketData(self, mode, exchange_tokens):
        self.calls.append((mode, exchange_tokens))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_complete_batch_accepts_exact_set():
    assert set(require_complete_quote_chunk(["1", "2"], payload("2", "1"))) == {"1", "2"}


def test_partial_success_status_is_not_full_coverage():
    reject("MISSING_TOKEN", ["1", "2"], payload("1"))


def test_unexpected_token_is_rejected():
    reject("UNEXPECTED_TOKEN", ["1"], payload("2"))


def test_duplicate_quote_identity_is_rejected():
    reject("DUPLICATE_TOKEN", ["1"], payload("1", "1"))


def test_missing_token_field_is_rejected():
    reject("MISSING_TOKEN", ["1"], {"status": True, "data": {"fetched": [{}]}})


def test_malformed_response_is_rejected():
    reject("MALFORMED_RESPONSE", ["1"], {"status": True, "data": {"fetched": None}})


def test_false_status_is_rejected():
    reject("BAD_STATUS", ["1"], {"status": False, "data": {"fetched": [{"symbolToken": "1"}]}})


def test_nonempty_unfetched_is_rejected_even_with_fetched():
    reject("UNFETCHED_PRESENT", ["1"], payload("1", unfetched=[{"symbolToken": "1"}]))


def test_duplicate_request_is_rejected():
    reject("DUPLICATE_REQUEST", ["1", "1"], payload("1"))


def test_empty_request_is_rejected_by_helper():
    reject("INVALID_REQUEST", [], payload())


def test_transient_partial_response_recovers_on_bounded_retry(monkeypatch):
    fetch = load_real_fetch_chunked(monkeypatch)
    api = FakeApi([payload("1"), payload("1", "2")])
    quotes, failures = fetch(api, ["1", "2"])
    assert (set(quotes), failures, len(api.calls)) == ({"1", "2"}, 0, 2)


def test_retry_exhaustion_discards_incomplete_chunk(monkeypatch):
    fetch = load_real_fetch_chunked(monkeypatch)
    api = FakeApi([payload("1")] * 4)
    assert fetch(api, ["1", "2"]) == ({}, 1)
    assert len(api.calls) == 4


def test_later_chunk_failure_discards_earlier_good_quotes(monkeypatch):
    fetch = load_real_fetch_chunked(monkeypatch)
    api = FakeApi([payload("1"), payload()] + [payload()] * 3)
    assert fetch(api, ["1", "2"], size=1) == ({}, 1)
    assert len(api.calls) == 5


def test_transient_network_error_recovers(monkeypatch):
    fetch = load_real_fetch_chunked(monkeypatch)
    api = FakeApi([TimeoutError("private-info"), payload("1")])
    assert fetch(api, ["1"]) == ({"1": {"symbolToken": "1"}}, 0)


def test_error_logs_do_not_echo_exception_payload(monkeypatch, capsys):
    fetch = load_real_fetch_chunked(monkeypatch)
    api = FakeApi([RuntimeError("DO_NOT_PRINT_PRIVATE_DATA")] * 4)
    assert fetch(api, ["1"]) == ({}, 1)
    assert "DO_NOT_PRINT_PRIVATE_DATA" not in capsys.readouterr().out


def test_invalid_batch_size_blocks_before_broker(monkeypatch):
    fetch = load_real_fetch_chunked(monkeypatch)
    api = FakeApi([])
    with pytest.raises(ValueError, match="positive"):
        fetch(api, ["1"], size=0)
    assert api.calls == []


def test_duplicate_requested_tokens_block_before_broker(monkeypatch):
    fetch = load_real_fetch_chunked(monkeypatch)
    api = FakeApi([])
    with pytest.raises(QuoteBatchIntegrityError, match="DUPLICATE_REQUEST"):
        fetch(api, ["1", "1"])
    assert api.calls == []

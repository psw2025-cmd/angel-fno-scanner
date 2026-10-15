import gspread
import pytest

from tools import sheets_quota


class _Resp:
    def __init__(self, code):
        self.status_code = code
        self.text = "{}"

    def json(self):
        return {"error": {"code": self.status_code, "message": "Quota exceeded for quota metric", "status": "X"}}


def _err(code):
    return gspread.exceptions.APIError(_Resp(code))


@pytest.fixture(autouse=True)
def _nosleep(monkeypatch):
    monkeypatch.setattr(sheets_quota, "_sleep", lambda s: None)


def test_retries_429_then_succeeds():
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise _err(429)
        return "ok"

    assert sheets_quota.with_retry(fn)() == "ok"
    assert len(calls) == 3


def test_persistent_429_fails_closed_after_bounded_attempts():
    calls = []

    def fn():
        calls.append(1)
        raise _err(429)

    with pytest.raises(gspread.exceptions.APIError):
        sheets_quota.with_retry(fn)()
    assert len(calls) == len(sheets_quota.RETRY_DELAYS) + 1


def test_non_quota_error_not_retried():
    calls = []

    def fn():
        calls.append(1)
        raise _err(400)

    with pytest.raises(gspread.exceptions.APIError):
        sheets_quota.with_retry(fn)()
    assert len(calls) == 1


def test_install_is_idempotent():
    from gspread import http_client

    original = http_client.HTTPClient.request
    try:
        sheets_quota.install()
        first = http_client.HTTPClient.request
        assert sheets_quota.install() is False
        assert http_client.HTTPClient.request is first
    finally:
        http_client.HTTPClient.request = original


def test_scanner_worksheet_cache_avoids_repeat_metadata_reads():
    import scanner

    scanner._WORKSHEET_CACHE.clear()
    calls = []

    class Book:
        id = "book-1"

        def worksheet(self, title):
            calls.append(title)
            return object()

    book = Book()
    a = scanner.worksheet(book, "FORENSIC_LIVE")
    b = scanner.worksheet(book, "FORENSIC_LIVE")
    assert a is b
    assert calls == ["FORENSIC_LIVE"]

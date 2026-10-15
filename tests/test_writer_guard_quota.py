import gspread
import pytest

import writer_guard


class _Resp429:
    status_code = 429
    text = "{}"

    def json(self):
        return {"error": {"code": 429, "message": "Quota exceeded for quota metric 'Read requests'", "status": "RESOURCE_EXHAUSTED"}}


def _quota_error():
    return gspread.exceptions.APIError(_Resp429())


class _WS:
    def __init__(self):
        self.rows = []
        self.headers = None

    def row_values(self, n):
        return self.headers or []

    def update(self, range_name, values, value_input_option):
        self.headers = values[0]

    def append_row(self, row, value_input_option):
        self.rows.append(row)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("WRITER_ID", "market_bot")
    monkeypatch.setenv("ALLOW_PRODUCTION_WRITES", "1")
    monkeypatch.setenv("RUN_ID", "run-1")
    monkeypatch.setenv("GIT_SHA", "cc057b9cf4ebf0aed8b352d62e109b161fba649c")
    monkeypatch.setattr(writer_guard, "_sleep", lambda s: None)


def test_quota_error_on_read_is_retried_and_does_not_create_sheet():
    ws = _WS()
    calls = {"worksheet": 0, "add": 0}

    class SH:
        def worksheet(self, title):
            calls["worksheet"] += 1
            if calls["worksheet"] < 3:
                raise _quota_error()
            return ws

        def add_worksheet(self, **kw):
            calls["add"] += 1
            raise AssertionError("must not create an existing sheet")

    writer_guard.append_sheet_provenance(SH(), "SINK", 5, "2026-10-15T13:00:00+05:30")
    assert calls["add"] == 0
    assert len(ws.rows) == 1


def test_missing_sheet_is_created():
    ws = _WS()

    class SH:
        def worksheet(self, title):
            raise gspread.exceptions.WorksheetNotFound(title)

        def add_worksheet(self, **kw):
            return ws

    writer_guard.append_sheet_provenance(SH(), "SINK", 1, "t")
    assert len(ws.rows) == 1


def test_non_quota_error_propagates():
    class SH:
        def worksheet(self, title):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        writer_guard.append_sheet_provenance(SH(), "SINK", 1, "t")


def test_persistent_quota_error_fails_closed():
    class SH:
        def worksheet(self, title):
            raise _quota_error()

    with pytest.raises(gspread.exceptions.APIError):
        writer_guard.append_sheet_provenance(SH(), "SINK", 1, "t")

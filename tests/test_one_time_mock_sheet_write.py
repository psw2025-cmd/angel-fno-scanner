"""No service credentials required for isolation and schema contract tests."""
import os
import pytest

from tools.mock_replay import build_replay
from tools.one_time_mock_sheet_write import evidence_rows, verify_locks, TARGET_TAB


def test_mock_sheet_receipt_is_never_live_verified(monkeypatch):
    for key, value in [("PAPER_MODE","1"), ("LIVE_ORDER_AUTHORITY","0"),
                       ("REAL_BROKER_ORDERS","0"), ("ALLOW_PRODUCTION_WRITES","0")]:
        monkeypatch.setenv(key,value)
    rows=evidence_rows(build_replay())
    values=dict(rows[1:])
    assert TARGET_TAB=="MOCK_REPLAY_EVIDENCE"
    assert len(rows)==19
    assert values["MOCK_PUBLICATION_STATUS"]=="SUCCESS_MOCK_REPLAY_ONLY"
    assert values["MOCK_OPTION_PREDICTIONS_STATUS"]=="VERIFIED_ACTIVE_MOCK_ONLY"
    assert values["PRODUCTION_DATA_SINK_WRITES"]=="0"
    assert "NOT LIVE" in values["DATA_CLASS"]
    assert "UNMODIFIED" in values["PRODUCTION_PUBLICATION_STATUS"]


@pytest.mark.parametrize("key,bad",[("PAPER_MODE","0"),("LIVE_ORDER_AUTHORITY","1"),
                                    ("REAL_BROKER_ORDERS","1"),("ALLOW_PRODUCTION_WRITES","1")])
def test_mock_sheet_writer_refuses_unsafe_environment(monkeypatch,key,bad):
    monkeypatch.setenv(key,bad)
    with pytest.raises(RuntimeError,match="Unsafe environment lock"):
        verify_locks()


def test_invalid_fixture_cannot_write():
    sample=build_replay()
    sample["live_verified"]=True
    with pytest.raises(RuntimeError,match="Invalid simulation"):
        evidence_rows(sample)


def test_forensic_audit_excludes_optional_mock_tab_but_checks_original_30():
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/"tools/forensic_sheet_repair.py").read_text()
    assert 'ws.title != "MOCK_REPLAY_EVIDENCE"' in source
    assert "if len(sheets) != 30:" in source

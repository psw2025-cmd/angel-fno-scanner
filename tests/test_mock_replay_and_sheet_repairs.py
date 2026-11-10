"""No live credentials needed: verify clear separation of mock and real evidence."""
import datetime as dt
import os

import pytest

from tools.mock_replay import build_replay
from tools.forensic_sheet_repair import build_fixes, FAILED_RUN_ID


def test_mock_replay_219_200_and_zero_real_calls(monkeypatch):
    for name, value in (("PAPER_MODE","1"),("LIVE_ORDER_AUTHORITY","0"),
                        ("REAL_BROKER_ORDERS","0")):
        monkeypatch.setenv(name,value)
    result=build_replay(now=dt.datetime(2026,11,11,4,0,tzinfo=dt.timezone.utc))
    assert result["underlyings"]==219
    assert result["ranked_ce_pe_contracts"]==200
    assert result["real_orders"]==0 and result["broker_calls"]==0
    assert result["sink_writes"]==0 and not result["live_verified"]
    assert result["stale_negative_control_rejected"]
    assert result["paper_lifecycle"]==["CREATED","ACK","FILLED","CLOSED"]


@pytest.mark.parametrize("name,wrong",[("PAPER_MODE","0"),("LIVE_ORDER_AUTHORITY","1"),
                                        ("REAL_BROKER_ORDERS","1")])
def test_replay_refuses_real_order_authority(monkeypatch,name,wrong):
    monkeypatch.setenv(name,wrong)
    with pytest.raises(RuntimeError,match="PAPER-only lock mismatch"):
        build_replay(now=dt.datetime.now(dt.timezone.utc))


def test_sheet_repairs_target_exact_nine_and_protect_newer_publication():
    patches=build_fixes("Asia/Kolkata",True)
    assert sum(map(len,patches.values()))==9
    assert patches["PUBLICATION_STATUS"]["A2"]=="FAILED_PARTIAL"
    assert FAILED_RUN_ID in patches["OPTION_PREDICTIONS"]["G2"]
    assert "A5:A204" in patches["Formula Checks"]["C10"]
    assert "HEARTBEAT!E2" not in patches["Formula Checks"]["E3"]
    assert "BLOCKED" in patches["Formula Checks"]["E8"]
    assert "SUCCESS" in patches["CLOUD_STATUS"]["B9"]
    assert sum(map(len,build_fixes("Asia/Kolkata",False).values()))==7
    assert "PUBLICATION_STATUS" not in build_fixes("Asia/Kolkata",False)


def test_unknown_spreadsheet_timezone_cannot_claim_freshness():
    patch=build_fixes("Etc/UTC",True)["Formula Checks"]["E3"]
    assert ',"BLOCKED")' in patch
    assert "PASS" not in patch

def test_google_sheet_legacy_ist_alias_enables_strict_live_age_gate():
    """Google Sheets reports Asia/Calcutta, the IANA alias of Asia/Kolkata."""
    formulas=build_fixes("Asia/Calcutta", True)
    gate=formulas["Formula Checks"]["E3"]
    assert "HEARTBEAT!A2" in gate
    assert "CE_PE_RANK!W5:W204" in gate
    assert "qage<=120" in gate and "wage<=60" in gate
    assert '"PASS"' in gate

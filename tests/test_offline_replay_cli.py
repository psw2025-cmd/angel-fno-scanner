"""Smoke-test actual -m CLI invocation (not only module imports in pytest)."""
import json
import os
import subprocess
import sys


def test_offline_replay_cli_real_python_process(tmp_path):
    target=tmp_path/"mock_replay.json"
    env={**os.environ, "PAPER_MODE":"1", "LIVE_ORDER_AUTHORITY":"0",
         "REAL_BROKER_ORDERS":"0"}
    process=subprocess.run([sys.executable,"-m","tools.mock_replay","--mock-replay",
                            "--output",str(target)],env=env,capture_output=True,
                           text=True,timeout=30)
    assert process.returncode==0, (process.stderr or process.stdout)[-800:]
    result=json.loads(target.read_text(encoding="utf-8"))
    assert result["mode"]=="MOCK_REPLAY"
    assert result["underlyings"]==219 and result["ranked_ce_pe_contracts"]==200
    assert result["real_orders"]==result["sink_writes"]==result["broker_calls"]==0
    assert result["live_verified"] is False
    assert "MOCK_REPLAY_PASS" in process.stdout

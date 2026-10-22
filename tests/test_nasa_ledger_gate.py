"""NASA ledger fail-closed regression contract; no cloud secrets or network."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from nasa_ledger_gate import evaluate_ledger, main

SHA = "a" * 40


def ledger():
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "generated_at_utc": ts,
        "summary": {"PASS": 25, "FAIL": 0, "BLOCKED": 0, "NOT_RUN": 0},
        "checks": [
            {"id": f"P-{i:02d}", "status": "PASS", "source_sha": SHA,
             "timestamp": ts, "evidence": {"reason": "independent executed readback", "details": {"exit": 0}}}
            for i in range(1, 26)
        ],
    }


def test_valid_current_complete_ledger_passes():
    assert evaluate_ledger(ledger(), SHA) == []


def test_blocked_check_never_green():
    p = ledger()
    p["checks"][4]["status"] = "BLOCKED"
    p["summary"]["PASS"] -= 1
    p["summary"]["BLOCKED"] += 1
    assert "unverified:P-05:BLOCKED" in evaluate_ledger(p, SHA)


def test_failed_check_never_green():
    p = ledger()
    p["checks"][7]["status"] = "FAIL"
    p["summary"]["PASS"] -= 1
    p["summary"]["FAIL"] += 1
    assert "unverified:P-08:FAIL" in evaluate_ledger(p, SHA)


def test_duplicate_or_missing_check_fails():
    p = ledger()
    p["checks"][-1]["id"] = "P-24"
    assert "incomplete_or_duplicate_check_ids" in evaluate_ledger(p, SHA)


def test_stale_or_wrong_sha_fails():
    p = ledger()
    p["checks"][0]["source_sha"] = "b" * 40
    assert "source_sha_mismatch:P-01" in evaluate_ledger(p, SHA)


def test_stale_timestamp_fails():
    p = ledger()
    p["generated_at_utc"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    assert "stale_or_future_generated_at" in evaluate_ledger(p, SHA)


def test_summary_disagreement_fails():
    p = ledger()
    p["summary"]["PASS"] = 24
    assert "summary_mismatch" in evaluate_ledger(p, SHA)


def test_unproven_pass_fails():
    p = ledger()
    p["checks"][0]["evidence"] = {"reason": "fixture only", "details": None}
    assert "missing_pass_details:P-01" in evaluate_ledger(p, SHA)


def test_invalid_json_and_missing_file_exit_nonzero(tmp_path):
    path = tmp_path / "missing.json"
    assert main(["--ledger", str(path), "--expect-sha", SHA]) == 1
    path.write_text("{not json", encoding="utf-8")
    assert main(["--ledger", str(path), "--expect-sha", SHA]) == 1


def test_cli_negative_ledger_exit_nonzero(tmp_path):
    path = tmp_path / "ledger.json"
    p = ledger()
    p["checks"][0]["status"] = "BLOCKED"
    p["summary"]["PASS"] -= 1
    p["summary"]["BLOCKED"] += 1
    path.write_text(json.dumps(p), encoding="utf-8")
    assert main(["--ledger", str(path), "--expect-sha", SHA]) == 1

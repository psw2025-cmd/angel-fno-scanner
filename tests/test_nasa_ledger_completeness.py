import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

def test_nasa_ledger_all_checks_have_truthful_status(monkeypatch):
    script = ROOT / "tools" / "nasa_daily_proof.py"
    spec = importlib.util.spec_from_file_location("nasa_daily_proof_under_test", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    def mock_cmd(argv, timeout=50):
        cmd_str = " ".join(argv)
        if "ls-files" in cmd_str:
            return (0, "", "")
        if "pytest" in cmd_str:
            return (0, "280 passed in 10s", "")
        if "verify_sheets_bq_reconciliation" in cmd_str:
            return (0, '"checksum_sha256_16": "3f6153d1e221ae43"', "")
        if "memory_guard" in cmd_str:
            return (0, "Guarding 6 files", "")
        return (0, "status: PASS", "")
    monkeypatch.setattr(mod, "cmd", mock_cmd)
    monkeypatch.setattr(mod, "scan_emoji", lambda value: False)
    monkeypatch.delenv("N8N_HEALTH_URL", raising=False)
    monkeypatch.setenv("NASA_ENABLE_CLOUD_VERIFY", "0")
    result_code = mod.run()
    assert result_code == 0
    output = ROOT / "proof-output" / "PROVEN_PROOF_LEDGER.json"
    result = json.loads(output.read_text(encoding="utf-8"))
    template = json.loads((ROOT / "docs" / "PROVEN_PROOF_LEDGER.json").read_text(encoding="utf-8"))
    assert len(result["checks"]) == len(template["checks"]) == 25
    assert result["summary"]["BLOCKED"] >= 3
    for item in result["checks"]:
        assert item["status"] in {"PASS", "FAIL", "BLOCKED", "NOT_APPLICABLE", "NOT_RUN"}
        n = int(item["id"].split("-")[-1])
        if n in {24, 25}:
            assert item["status"] == "NOT_APPLICABLE"
        elif n in {21, 22, 23}:
            assert item["status"] in {"PASS", "BLOCKED"}
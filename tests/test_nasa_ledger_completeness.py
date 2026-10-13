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


def test_cmd_stdout_truncation_fix():
    import sys
    script = ROOT / "tools" / "nasa_daily_proof.py"
    spec = importlib.util.spec_from_file_location("nasa_daily_proof_under_test", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # 1. Full stdout without truncation (len > 4000)
    code, out, err = mod.cmd([sys.executable, "-c", "import sys; sys.stdout.write('A' * 8000)"])
    assert code == 0
    assert len(out) == 8000
    assert err == ""

    # 2. Bounded stdout when max_stdout is explicitly set
    code, out, err = mod.cmd([sys.executable, "-c", "import sys; sys.stdout.write('B' * 8000)"], max_stdout=4000)
    assert code == 0
    assert len(out) == 4000
    assert out.endswith("BBBB")


def test_cmd_nonzero_exit_and_error_handling():
    import sys
    script = ROOT / "tools" / "nasa_daily_proof.py"
    spec = importlib.util.spec_from_file_location("nasa_daily_proof_under_test", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Nonzero exit code and stderr capture
    code, out, err = mod.cmd([sys.executable, "-c", "import sys; sys.stderr.write('custom_error'); sys.exit(42)"])
    assert code == 42
    assert "custom_error" in err

    # Exception / nonexistent executable handling
    code, out, err = mod.cmd(["nonexistent_executable_binary_12345"])
    assert code == -1
    assert len(err) > 0


def test_p11_zero_scanned_files_fails_closed(monkeypatch):
    script = ROOT / "tools" / "nasa_daily_proof.py"
    spec = importlib.util.spec_from_file_location("nasa_daily_proof_under_test", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def mock_cmd(argv, timeout=50, max_stdout=None):
        cmd_str = " ".join(argv)
        if "ls-files" in cmd_str:
            return (0, "", "")  # Simulated empty git ls-files
        return (0, '{"status": "PASS", "hashes_matched": true, "production_untouched": true, "fixture_restore_labeled": true, "real_snapshots_restored": ["x"]}', "")

    monkeypatch.setattr(mod, "cmd", mock_cmd)
    monkeypatch.setattr(mod, "scan_emoji", lambda value: False)
    monkeypatch.delenv("N8N_HEALTH_URL", raising=False)
    monkeypatch.setenv("NASA_ENABLE_CLOUD_VERIFY", "0")

    result_code = mod.run()
    assert result_code == 0
    output = ROOT / "proof-output" / "PROVEN_PROOF_LEDGER.json"
    result = json.loads(output.read_text(encoding="utf-8"))
    check11 = next(c for c in result["checks"] if c["id"] == "P-11")
    assert check11["status"] == "FAIL"
    assert check11["evidence"]["details"]["scanned_total"] == 0


def test_p14_truncated_json_fails_closed(monkeypatch):
    script = ROOT / "tools" / "nasa_daily_proof.py"
    spec = importlib.util.spec_from_file_location("nasa_daily_proof_under_test", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def mock_cmd(argv, timeout=50, max_stdout=None):
        cmd_str = " ".join(argv)
        if "cold_restore_drill.py" in cmd_str:
            return (0, '{"status": "PASS", truncated_invalid_json', "")
        if "ls-files" in cmd_str:
            return (0, "\n".join([f"file_{i}.txt" for i in range(100)]), "")
        return (0, "status: PASS", "")

    monkeypatch.setattr(mod, "cmd", mock_cmd)
    monkeypatch.setattr(mod, "scan_emoji", lambda value: False)
    monkeypatch.delenv("N8N_HEALTH_URL", raising=False)
    monkeypatch.setenv("NASA_ENABLE_CLOUD_VERIFY", "0")

    result_code = mod.run()
    assert result_code == 0
    output = ROOT / "proof-output" / "PROVEN_PROOF_LEDGER.json"
    result = json.loads(output.read_text(encoding="utf-8"))
    check14 = next(c for c in result["checks"] if c["id"] == "P-14")
    assert check14["status"] == "FAIL"
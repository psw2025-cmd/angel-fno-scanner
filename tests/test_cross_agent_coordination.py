from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]

def test_cross_agent_coordination_assets_exist():
    assert (ROOT / "docs" / "CROSS_AGENT_COORDINATION_V1.md").exists()
    assert (ROOT / "schemas" / "cross_agent_packet.schema.json").exists()
    assert (ROOT / "scripts" / "validate_cross_agent_packet.py").exists()
    assert (ROOT / "tools" / "agy_cross_agent_packet.ps1").exists()

def test_validator_accepts_minimal_valid_packet(tmp_path):
    module_path = ROOT / "scripts" / "validate_cross_agent_packet.py"
    spec = importlib.util.spec_from_file_location("packet_validator", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    import json
    packet = {
        "claim_id": "AGY-123456",
        "claiming_agent": "AGY_CLI",
        "claim_time_ist": "2026-09-30T00:00:00+05:30",
        "host_or_runtime": "WINDOWS",
        "repo": "psw2025-cmd/angel-fno-scanner",
        "claim": "test",
        "observation": "test",
        "primary_evidence": "test",
        "before_state": "test",
        "action_taken": "test",
        "after_state": "test",
        "safety_state": "PAPER",
        "secrets_redacted": True,
        "peer_check_request": "verify",
        "status": "WAITING_FOR_PEER",
    }
    p = tmp_path / "packet.json"
    p.write_text(json.dumps(packet), encoding="utf-8")
    assert mod.validate(p) == []

def test_protocol_requires_two_party_resolution():
    text = (ROOT / "docs" / "CROSS_AGENT_COORDINATION_V1.md").read_text(encoding="utf-8")
    assert "RESOLVED_TWO_PARTY" in text
    assert "DISPUTED" in text
    assert "single-writer" in text
    assert "100% market prediction accuracy" in text

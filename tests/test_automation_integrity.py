from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_market_bot_runs_short_repeating_cycles_without_cancel():
    text = (ROOT / ".github/workflows/market_bot.yml").read_text(encoding="utf-8-sig")
    assert "cron: '45 3 * * 1-5'" in text
    assert "github.event_name == 'schedule' && '24300' || '300'" in text
    assert "timeout-minutes: 420" in text
    assert "cancel-in-progress: false" in text  # concurrency cancel-in-progress false is intentional for single_writer to prevent kill collisions


def test_provenance_verifier_is_read_only():
    text = (ROOT / "scripts/sync_cycle_provenance_to_bq.py").read_text(encoding="utf-8")
    forbidden = (
        "load_table_from_json",
        "insert_rows",
        "WRITE_APPEND",
        "WRITE_TRUNCATE",
        "ALTER TABLE",
        "DELETE FROM",
        "UPDATE ",
    )
    for token in forbidden:
        assert token not in text


def test_listener_disables_unsafe_auto_remediation():
    text = (ROOT / "scripts/n8n_readonly_listener.py").read_text(encoding="utf-8")
    assert 'if self.path == "/auto-remediate"' in text
    assert '"status": "DISABLED"' in text
    assert "ALTER TABLE" not in text
    assert "sync_cycle_provenance_to_bq.py" not in text


def test_generated_workflows_fail_closed_without_fake_defaults():
    folder = ROOT / "n8n_automation/workflows"
    files = sorted(folder.glob("*.json"))
    assert len(files) >= 6, f"Expected >=6 workflow files, found {len(files)}"
    combined = ""
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["id"].startswith("angel-fno-")
        combined += path.read_text(encoding="utf-8")
    assert "|| 219" not in combined
    assert "provenance_aligned: true" not in combined
    assert "REMEDIATED_VERIFIED" not in combined
    assert "auto-remediate" not in combined
    assert "read_only" in combined


def test_n8n_sync_enforces_integrity():
    text = (ROOT / "tools/n8n_sync.py").read_text(encoding="utf-8")
    assert "PRAGMA foreign_keys=ON" in text
    assert "PRAGMA foreign_key_check" in text
    assert "repair_missing_history" in text
    assert "backup_db" in text


def test_nightly_verify_installs_pytest():
    text = (ROOT / ".github/workflows/nightly_verify.yml").read_text(encoding="utf-8")
    assert "pip install -r requirements.txt pytest" in text

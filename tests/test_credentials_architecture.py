import json
import pytest
import credentials
import scanner
import angel_prediction_engine as ape


def test_load_env_populates_os_environ_without_overwriting(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Test comment\n"
        "TEST_NEW_KEY=hello_world\n"
        "TEST_QUOTED='single_quoted'\n"
        "TEST_DOUBLE=\"double_quoted\"\n"
        "TEST_EXISTING=new_val\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_EXISTING", "original_val")
    monkeypatch.delenv("TEST_NEW_KEY", raising=False)
    monkeypatch.delenv("TEST_QUOTED", raising=False)
    monkeypatch.delenv("TEST_DOUBLE", raising=False)

    loaded = credentials.load_env(str(env_file))
    assert loaded["TEST_NEW_KEY"] == "hello_world"
    assert loaded["TEST_QUOTED"] == "single_quoted"
    assert loaded["TEST_DOUBLE"] == "double_quoted"
    assert "TEST_EXISTING" not in loaded  # was already in environ, not overwritten
    assert credentials.os.environ["TEST_EXISTING"] == "original_val"


def test_load_service_account_from_gac_file(monkeypatch, tmp_path):
    sa_file = tmp_path / "gcp-sa.json"
    sa_file.write_text(json.dumps({"type": "service_account", "project_id": "test-gac-project"}), encoding="utf-8")
    monkeypatch.delenv("SHEETS_KEY_JSON", raising=False)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(sa_file))
    monkeypatch.setattr("credentials.DEFAULT_KEY_PATHS", [])

    info = credentials.load_service_account()
    assert info["type"] == "service_account"
    assert info["project_id"] == "test-gac-project"


def test_load_service_account_from_sheets_key_json_file_path(monkeypatch, tmp_path):
    sa_file = tmp_path / "custom-sa.json"
    sa_file.write_text(json.dumps({"type": "service_account", "project_id": "test-path-project"}), encoding="utf-8")
    monkeypatch.setenv("SHEETS_KEY_JSON", str(sa_file))
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setattr("credentials.DEFAULT_KEY_PATHS", [])

    info = credentials.load_service_account()
    assert info["type"] == "service_account"
    assert info["project_id"] == "test-path-project"


def test_load_service_account_from_sheets_key_json_raw_string(monkeypatch):
    raw = json.dumps({"type": "service_account", "project_id": "test-raw-project"})
    monkeypatch.setenv("SHEETS_KEY_JSON", raw)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setattr("credentials.DEFAULT_KEY_PATHS", [])

    info = credentials.load_service_account()
    assert info["type"] == "service_account"
    assert info["project_id"] == "test-raw-project"


def test_load_service_account_fails_closed_when_all_missing(monkeypatch):
    monkeypatch.delenv("SHEETS_KEY_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setattr("credentials.DEFAULT_KEY_PATHS", [])

    with pytest.raises(RuntimeError, match="Google Sheets service account credentials not found"):
        credentials.load_service_account()


def test_scanner_angel_login_fails_cleanly_without_keyerror(monkeypatch):
    monkeypatch.delenv("ANGEL_CLIENT_CODE", raising=False)
    monkeypatch.delenv("ANGEL_API_KEY", raising=False)
    monkeypatch.delenv("ANGEL_PIN", raising=False)
    monkeypatch.delenv("ANGEL_TOTP_SEED", raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        scanner.angel_login()
    assert "Angel One credentials are required only when broker access is invoked" in str(excinfo.value)
    assert "missing environment variables" in str(excinfo.value)


def test_prediction_engine_get_angel_client_fails_cleanly(monkeypatch):
    monkeypatch.delenv("ANGEL_CLIENT_CODE", raising=False)
    monkeypatch.delenv("ANGEL_API_KEY", raising=False)
    monkeypatch.delenv("ANGEL_PIN", raising=False)
    monkeypatch.delenv("ANGEL_TOTP_SEED", raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        ape.get_angel_client()
    assert "Angel One credentials are required only for live broker access" in str(excinfo.value)

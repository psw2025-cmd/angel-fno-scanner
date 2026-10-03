from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def test_scheduled_runtime_covers_nse_close():
    workflow = (ROOT / ".github/workflows/market_bot.yml").read_text(encoding="utf-8")
    m = re.search(r"MAX_RUNTIME_SECONDS:.*?'(\d+)'", workflow)
    assert m
    assert int(m.group(1)) >= 24300
    timeout = re.search(r"timeout-minutes:\s*(\d+)", workflow)
    assert timeout and int(timeout.group(1)) >= 435

def test_angel_credentials_have_no_source_defaults():
    source = (ROOT / "angel_prediction_engine.py").read_text(encoding="utf-8")
    for key in ("ANGEL_API_KEY", "ANGEL_CLIENT_CODE", "ANGEL_PIN", "ANGEL_TOTP_SEED"):
        assert not re.search(rf'os\.getenv\("{key}",\s*"[^"]+"\)', source)

def test_prediction_engine_uses_current_fno_close():
    source = (ROOT / "angel_prediction_engine.py").read_text(encoding="utf-8")
    assert "return 555 <= mins <= 940" in source
    assert "return 900 <= mins <= 940" in source


def test_paper_safety_and_zero_real_orders():
    """
    Mandatory Rule: Section 29 of AGENTS.md & Section 14 of 4.txt.
    PAPER / ANALYZER = ON
    LIVE ORDER AUTHORITY = OFF
    REAL BROKER ORDERS = 0
    Verifies that no real broker order placement APIs exist in production scripts.
    """
    for script_name in ("scanner.py", "angel_prediction_engine.py", "agent_cli.py"):
        code = (ROOT / script_name).read_text(encoding="utf-8")
        assert "placeOrder" not in code, f"Forbidden live order method found in {script_name}"
        assert "orderPlacement" not in code, f"Forbidden live order method found in {script_name}"
        assert "modifyOrder" not in code, f"Forbidden live order method found in {script_name}"
        assert "cancelOrder" not in code, f"Forbidden live order method found in {script_name}"


def test_mock_leakage_prevention():
    """
    Verifies that mock frameworks, test doubles, or synthetic fixtures never leak into production runtime engines.
    """
    for script_name in ("scanner.py", "angel_prediction_engine.py", "agent_cli.py", "credentials.py"):
        code = (ROOT / script_name).read_text(encoding="utf-8")
        assert "unittest.mock" not in code, f"Mock leakage detected in {script_name}"
        assert "pytest" not in code, f"Pytest import detected in production script {script_name}"
        assert "MagicMock" not in code, f"MagicMock detected in {script_name}"


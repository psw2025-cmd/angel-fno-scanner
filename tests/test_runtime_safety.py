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

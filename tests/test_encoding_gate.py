import importlib.util
from pathlib import Path
import pytest
p=Path(__file__).resolve().parents[1]/"tools"/"encoding_source_gate.py"
spec=importlib.util.spec_from_file_location("gate",p)
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
def test_ascii(): assert gate.check("a.py",b"print('[PASS]')\n")==[]
def test_syntax(): assert any("syntax" in e for e in gate.check("a.py",b"print('x'\n"))
def test_emoji(): assert any("U+1F7E2" in e for e in gate.check("a.py","print('\U0001F7E2')\n".encode()))
def test_legacy_unicode():
    b="x='caf\u00e9'\n".encode()
    assert gate.check("a.py",b,b)==[]
def test_bom(): assert gate.check("a.py",b"\xef\xbb\xbfprint('ok')\n")==[]
def test_bad_utf8(): assert gate.check("a.py",b"\xff")
def test_cp1252():
    with pytest.raises(UnicodeEncodeError): "\U0001F7E2".encode("cp1252")
    assert "[PASS]".encode("cp1252")==b"[PASS]"

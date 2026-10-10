import importlib.util
import sys
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[1] / "tools" / "encoding_source_gate.py"
spec = importlib.util.spec_from_file_location("gate", path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def test_ascii():
    assert gate.check("a.py", b"print('[PASS]')\n") == []


def test_syntax():
    assert any("syntax" in e for e in gate.check("a.py", b"print('x'\n"))


def test_emoji():
    assert any("U+1F7E2" in e for e in gate.check("a.py", "print('\U0001F7E2')\n".encode()))


def test_legacy_unicode():
    source = "x='caf\u00e9'\n".encode()
    assert gate.check("a.py", source, source) == []


def test_bom():
    assert gate.check("a.py", b"\xef\xbb\xbfprint('ok')\n") == []


def test_bad_utf8():
    assert gate.check("a.py", b"\xff")


def test_base_ref_rejects_new_emoji(monkeypatch, capsys):
    source = "print('\U0001F7E2')\n".encode()

    def fake_git(*args):
        if args[0] == "rev-parse":
            return b"basehash\n"
        if args[0] == "diff":
            return b"sample.py\0"
        if args[0] == "show":
            return b"print('ok')\n" if args[1] == "basehash:sample.py" else source
        raise AssertionError(args)

    monkeypatch.setattr(gate, "git", fake_git)
    monkeypatch.setattr(sys, "argv", ["encoding_source_gate.py", "--base-ref", "basehash"])
    assert gate.main() == 1
    assert "U+1F7E2" in capsys.readouterr().out


def test_base_ref_accepts_existing_unicode(monkeypatch, capsys):
    source = "x='caf\u00e9'\n".encode()

    def fake_git(*args):
        if args[0] == "rev-parse":
            return b"basehash\n"
        if args[0] == "diff":
            return b"sample.py\0"
        if args[0] == "show":
            return source
        raise AssertionError(args)

    monkeypatch.setattr(gate, "git", fake_git)
    monkeypatch.setattr(sys, "argv", ["encoding_source_gate.py", "--base-ref", "basehash"])
    assert gate.main() == 0
    assert "mode=base" in capsys.readouterr().out


def test_cp1252():
    with pytest.raises(UnicodeEncodeError):
        "\U0001F7E2".encode("cp1252")
    assert "[PASS]".encode("cp1252") == b"[PASS]"

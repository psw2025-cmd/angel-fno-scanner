import argparse
import contextlib
import io
import json
import pytest
import agent_cli

def test_json_only_exception_returns_machine_readable_blocked(monkeypatch):
    def broken():
        raise RuntimeError('external source unavailable')
    monkeypatch.setattr(agent_cli, 'run_full_verification', broken)
    output=io.StringIO()
    with contextlib.redirect_stdout(output), pytest.raises(SystemExit) as e:
        agent_cli.handle_verify(argparse.Namespace(json_only=True, format='human'))
    assert e.value.code == 1
    data=json.loads(output.getvalue())
    assert data['status']=='BLOCKED'
    assert data['error_type']=='RuntimeError'
    assert 'external source unavailable' not in data['reason']

def test_no_emoji_in_print_source():
    from pathlib import Path
    import re
    src=Path(agent_cli.__file__).read_text(encoding='utf-8')
    assert not any('print(' in line and re.search('[\U0001F300-\U0001FAFF\u2600-\u27BF]',line) for line in src.splitlines())
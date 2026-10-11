"""Prevent accidental production publication on push and static-gate drift."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'market_bot.yml'
READINESS = ROOT / 'scripts' / 'infra_readiness.py'


def test_market_writer_policy_fails_closed_on_push():
    text = WORKFLOW.read_text(encoding='utf-8-sig')
    expected = "ALLOW_PRODUCTION_WRITES: ${{ github.event_name == 'schedule' && '1' || (github.event_name == 'workflow_dispatch' && !inputs.dry_run && '1' || '0') }}"
    assert expected in text
    assert text.count('ALLOW_PRODUCTION_WRITES:') == 1
    assert "default: true" in text  # manual dispatch defaults to read-only


def test_static_readiness_validates_expression():
    text = READINESS.read_text(encoding='utf-8-sig')
    assert "expected_policy =" in text
    assert "writer_lines == [('market_bot.yml'" in text
    assert 'single_writer_static' in text


def test_no_other_workflow_declares_writer():
    for path in (ROOT / '.github' / 'workflows').glob('*.yml'):
        if path.name != 'market_bot.yml':
            assert all(line.split(':', 1)[1].strip().strip(chr(34)).strip(chr(39)) == '0' for line in path.read_text(encoding='utf-8-sig').splitlines() if 'ALLOW_PRODUCTION_WRITES:' in line), path.name

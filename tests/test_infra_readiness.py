from pathlib import Path
from types import SimpleNamespace as Field
import json
import subprocess
import sys
from scripts import infra_readiness as infra
import pytest


def test_schema_is_additive_and_conflicts_fail_closed():
    fields = [Field(name='symbol', field_type='STRING', mode='REQUIRED'),
              Field(name='source_timestamp', field_type='TIMESTAMP', mode='NULLABLE')]
    assert infra.schema_plan(fields) == ['run_id', 'git_sha', 'writer_id']
    assert len(fields) == 2
    with pytest.raises(ValueError):
        infra.schema_plan([Field(name='run_id', field_type='INTEGER', mode='NULLABLE')])
    with pytest.raises(ValueError):
        infra.schema_plan([Field(name='writer_id', field_type='STRING', mode='REPEATED')])


def test_sheet_preserves_conflicting_and_existing_runtime_rows():
    assert infra.sheet_plan([]) == 'initialize'
    assert infra.sheet_plan([['', '']]) == 'initialize'
    rows = [infra.HEADERS, ['old timestamp', '123', 'abc', 'market_bot', 'FORENSIC_LIVE', '219']]
    assert infra.sheet_plan(rows) == 'verified'
    assert len(rows) == 2
    with pytest.raises(ValueError):
        infra.sheet_plan([['wrong headers']])
    with pytest.raises(ValueError):
        infra.sheet_plan([[], ['orphan runtime row']])


def test_bigquery_only_patches_schema_and_verifies(monkeypatch, tmp_path):
    import google.cloud.bigquery as bq
    tables = {}
    calls = []
    class Client:
        def __init__(self, **kwargs):
            pass
        def get_table(self, name, **kwargs):
            calls.append(('get', name))
            return tables.setdefault(name, Field(schema=[], table_type='TABLE', to_api_repr=lambda: {'schema': 'metadata'}))
        def update_table(self, obj, fields, **kwargs):
            assert fields == ['schema']
            assert all(f.mode == 'NULLABLE' for f in obj.schema)
            calls.append(('patch', fields))
    monkeypatch.setattr(bq, 'Client', Client)
    (tmp_path / 'raw').mkdir()
    audit = infra.Audit(tmp_path, tmp_path)
    infra.bigquery_checks(audit, None, 'project', 'dataset', False)
    assert len([c for c in calls if c[0] == 'patch']) == 4
    assert len([c for c in calls if c[0] == 'get']) == 8
    assert len(audit.checks) == 4
    assert all(c['status'] == 'PASS' for c in audit.checks)


def test_verify_only_does_not_patch(monkeypatch, tmp_path):
    import google.cloud.bigquery as bq
    class Client:
        def __init__(self, **kwargs):
            pass
        def get_table(self, name, **kwargs):
            return Field(schema=[], table_type='TABLE', to_api_repr=lambda: {})
    monkeypatch.setattr(bq, 'Client', Client)
    (tmp_path / 'raw').mkdir()
    audit = infra.Audit(tmp_path, tmp_path)
    infra.bigquery_checks(audit, None, 'project', 'dataset', True)
    assert all(c['status'] == 'FAIL' for c in audit.checks)


def test_report_escapes_html_and_unknown_never_green(tmp_path):
    (tmp_path / 'raw').mkdir()
    audit = infra.Audit(tmp_path, tmp_path)
    audit.check('cloud', 'UNKNOWN', '<script>alert(1)</script>')
    assert infra.report(audit, 'VERIFY_ONLY') == 1
    assert '<script>' not in (tmp_path / 'SYSTEM_STATUS.html').read_text()
    result = json.loads((tmp_path / 'SYSTEM_STATUS.json').read_text())
    assert result['infrastructure'] == 'NOT_READY'
    assert result['runtime'] == 'NOT_PROVEN'
    for name in ['SYSTEM_STATUS.md', 'checks.csv', 'bigquery_schema.csv', 'symbols.csv', 'ci.csv', 'SHA256SUMS.csv']:
        assert (tmp_path / name).exists()


def test_provider_errors_do_not_leak_secrets(tmp_path):
    (tmp_path / 'raw').mkdir()
    audit = infra.Audit(tmp_path, tmp_path)
    def fail():
        raise RuntimeError('Bearer secret-token')
    audit.section('cloud', fail)
    infra.report(audit, 'VERIFY_ONLY')
    assert all('secret-token' not in p.read_text(encoding='utf-8-sig')
               for p in tmp_path.rglob('*') if p.is_file())


@pytest.mark.parametrize('verify_only', [False, True])
def test_sheet_only_initializes_header(monkeypatch, tmp_path, verify_only):
    import gspread
    calls = []
    class Worksheet:
        title = 'WRITE_PROVENANCE'
        headers = []
        def get_all_values(self):
            return []
        def update(self, **kwargs):
            assert kwargs == {'range_name': 'A1:F1', 'values': [infra.HEADERS], 'value_input_option': 'RAW'}
            self.headers = infra.HEADERS
            calls.append('header')
        def row_values(self, row):
            assert row == 1
            return self.headers
    ws = Worksheet()
    class Book:
        title = 'OPTION_SHEET'
        def worksheet(self, name):
            return ws
    class Client:
        def set_timeout(self, timeout):
            pass
        def open_by_key(self, key):
            return Book()
    monkeypatch.setattr(gspread, 'authorize', lambda _: Client())
    (tmp_path / 'raw').mkdir()
    audit = infra.Audit(tmp_path, tmp_path)
    infra.sheets_checks(audit, None, 'id', verify_only)
    assert calls == ([] if verify_only else ['header'])
    assert audit.checks[0]['status'] == ('FAIL' if verify_only else 'PASS')


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows PowerShell compatibility')
def test_windows_powershell_syntax(tmp_path):
    source = Path(infra.__file__).with_name('prepare_infra_readiness.ps1')
    parser = tmp_path / 'parse.ps1'
    parser.write_text("$tokens=$null; $parseErrors=$null\n"
                      "[System.Management.Automation.Language.Parser]::ParseFile('" +
                      str(source).replace("'", "''") +
                      "',[ref]$tokens,[ref]$parseErrors) | Out-Null\n"
                      "if ($parseErrors.Count) { $parseErrors; exit 1 }; exit 0\n")
    result = subprocess.run(['powershell.exe', '-NoProfile', '-File', str(parser)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr

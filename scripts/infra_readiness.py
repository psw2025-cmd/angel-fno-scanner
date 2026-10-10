"""Metadata-only preparation. Never imports scanner, engine, or writer helpers."""
import argparse
import ast
import csv
import datetime as dt
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
from zoneinfo import ZoneInfo

TABLES = ('option_predictions_live', 'market_news_sentiment',
          'prediction_calibration_log', 'next_day_gap_predictions')
FIELDS = ('run_id', 'git_sha', 'writer_id', 'source_timestamp')
HEADERS = ['Source Timestamp', 'Run ID', 'Git SHA', 'Writer ID', 'Sink', 'Record Count']
REPOSITORY = 'psw2025-cmd/angel-fno-scanner'


def schema_plan(schema):
    """Preserve timestamp-compatible existing fields; new values are strings in main."""
    existing = {f.name: f for f in schema}
    for name in FIELDS:
        if name in existing:
            field = existing[name]
            allowed = {'STRING', 'TIMESTAMP', 'DATETIME'} if name == 'source_timestamp' else {'STRING'}
            if field.field_type.upper() not in allowed or field.mode != 'NULLABLE':
                raise ValueError('Conflicting provenance field: ' + name)
    return [name for name in FIELDS if name not in existing]


def sheet_plan(values):
    if values and values[0] == HEADERS:
        return 'verified'
    if any(any(str(cell).strip() for cell in row) for row in values):
        raise ValueError('Nonempty WRITE_PROVENANCE has conflicting headers; preserved')
    return 'initialize'


class Audit:
    def __init__(self, repo, folder):
        self.repo, self.folder = repo, folder
        self.checks = []
        self.schema = []
        self.ci = []
        self.symbols = []

    def check(self, name, status, detail):
        self.checks.append(dict(check=name, status=status, detail=detail))

    def raw(self, name, data):
        (self.folder / 'raw' / name).write_text(
            json.dumps(data, indent=2, default=str), encoding='utf-8')

    def command(self, name, args):
        # Never save inherited environment, credentials, stderr, or arbitrary process arguments.
        result = subprocess.run(args, cwd=self.repo, capture_output=True, text=True,
                                timeout=60, encoding='utf-8', errors='replace')
        self.raw(name + '.json', {'command': args, 'exit_code': result.returncode,
                                 'stdout': result.stdout if result.returncode == 0 else '',
                                 'error': 'Command failed; stderr withheld' if result.returncode else None})
        if result.returncode:
            raise RuntimeError(name + ' failed')
        return result.stdout.strip()

    def section(self, name, action):
        try:
            action()
        except Exception as exc:
            # Provider exception messages can contain credentials/request payloads.
            self.check(name, 'UNKNOWN', 'Unable to verify (' + type(exc).__name__ +
                       '); check credentials, dependencies, access and connectivity')
            self.raw(name + '_error.json', {'exception_type': type(exc).__name__})


def local_checks(audit, offline):
    head = audit.command('git_head', ['git', 'rev-parse', 'HEAD'])
    audit.check('git_head', 'PASS', head)
    dirty = audit.command('git_status', ['git', 'status', '--porcelain'])
    audit.check('working_tree', 'FAIL' if dirty else 'PASS', 'Dirty' if dirty else 'Clean')
    if offline:
        audit.check('current_main', 'UNKNOWN', 'Offline: remote main not queried')
    else:
        remote = audit.command('remote_main', ['git', '-c', 'http.sslBackend=openssl',
                               'ls-remote', 'https://github.com/' + REPOSITORY + '.git',
                               'refs/heads/main']).split()[0]
        audit.check('current_main', 'PASS' if head == remote else 'FAIL',
                    'local=' + head + '; remote main=' + remote)
    manifest = json.loads((audit.repo / 'agent_manifest.json').read_text(encoding='utf-8-sig'))
    symbols = manifest['universe']['symbols']
    audit.symbols = [{'symbol': s} for s in symbols]
    tree = ast.parse((audit.repo / 'scanner.py').read_text(encoding='utf-8-sig'))
    default = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and
                t.id == 'EXPECTED_FNO_UNIVERSE_COUNT' for t in node.targets):
            default = ast.literal_eval(node.value)
    override = os.getenv('EXPECTED_FNO_UNIVERSE_COUNT', default)
    good = len(symbols) == len(set(symbols)) == manifest['universe']['total_symbols'] == 219
    good = good and str(default) == str(override) == '219'
    audit.check('219_symbol_config', 'PASS' if good else 'FAIL',
                f'manifest={len(symbols)}, unique={len(set(symbols))}, scanner default={default}, effective={override}; configuration only')
    workflows = audit.repo / '.github' / 'workflows'
    # Only market_bot may enable writes. Push events must fail closed.
    market = (workflows / 'market_bot.yml').read_text(encoding='utf-8-sig')
    writer_lines = []
    for workflow in workflows.glob('*.yml'):
        for line in workflow.read_text(encoding='utf-8-sig').splitlines():
            if re.match(r'^\s*ALLOW_PRODUCTION_WRITES\s*:', line) and line.split(':', 1)[1].strip().strip(chr(34)).strip(chr(39)) != '0':
                writer_lines.append((workflow.name, line.strip()))
    expected_policy = "github.event_name == 'schedule' && '1' || (github.event_name == 'workflow_dispatch' && !inputs.dry_run && '1' || '0')"
    good = writer_lines == [('market_bot.yml', 'ALLOW_PRODUCTION_WRITES: ${{ ' + expected_policy + ' }}')]
    good = good and market.count('python scanner.py') == 1
    good = good and 'WRITER_ID: market_bot' in market and 'group: market-bot' in market
    good = good and 'angel_prediction_engine.py --run-once' not in market
    guard = (audit.repo / 'writer_guard.py').read_text(encoding='utf-8-sig')
    good = good and 'AUTHORIZED_WRITER_ID = "market_bot"' in guard
    audit.check('single_writer_static', 'PASS' if good else 'FAIL',
                'Workflow/guard source inspection only; cross-runtime lease and IAM not proven')
    audit.check('runtime_provenance', 'NOT_PROVEN',
                'Requires next normal market_bot run: same run_id in sinks, fresh 219 symbols, no duplicates, one prediction cycle')


def github_checks(audit):
    sha = audit.command('ci_head', ['git', 'rev-parse', 'HEAD'])
    url = f'https://api.github.com/repos/{REPOSITORY}/actions/runs?head_sha={sha}&per_page=100'
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'infra-readiness'}
    token = os.getenv('GH_TOKEN') or os.getenv('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        runs = json.load(response)['workflow_runs']
    # Save metadata only, never headers or credentials. Only exact-SHA PR Tests qualify.
    audit.ci = [{k: run.get(k) for k in ('id', 'head_sha', 'name', 'path', 'status',
                 'conclusion', 'html_url', 'created_at')} for run in runs]
    audit.raw('github_ci.json', audit.ci)
    tests = sorted([r for r in audit.ci if r['path'] == '.github/workflows/pr_tests.yml'
                    and r['head_sha'] == sha], key=lambda r: r['id'], reverse=True)
    latest = tests[0] if tests else None
    status = 'UNKNOWN' if latest is None else ('PASS' if latest['conclusion'] == 'success'
             and latest['status'] == 'completed' else 'FAIL')
    audit.check('exact_sha_ci', status, json.dumps(latest) if latest else 'No exact-SHA PR Tests run found')


def google_credentials(repo):
    from google.oauth2 import service_account
    import google.auth
    scopes = ['https://www.googleapis.com/auth/cloud-platform',
              'https://www.googleapis.com/auth/spreadsheets']
    # Read only Google configuration; never load broker settings or import production modules.
    config = {k: os.getenv(k, '') for k in ('SHEETS_KEY_JSON', 'GOOGLE_APPLICATION_CREDENTIALS')}
    env_file = repo / '.env'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8-sig').splitlines():
            key, sep, value = line.partition('=')
            if sep and key.strip() in config and not config[key.strip()]:
                config[key.strip()] = value.strip().strip('\"\'')
    raw = config['SHEETS_KEY_JSON']
    if raw.lstrip().startswith('{'):
        return service_account.Credentials.from_service_account_info(json.loads(raw), scopes=scopes)
    candidates = [raw, config['GOOGLE_APPLICATION_CREDENTIALS'],
                  r'C:\AngelFNO_Workstation\secrets\gcp-service-account.json']
    for path in candidates:
        if path and Path(path).is_file():
            return service_account.Credentials.from_service_account_file(path, scopes=scopes)
    return google.auth.default(scopes=scopes)[0]


def bigquery_checks(audit, creds, project, dataset, verify_only):
    from google.cloud import bigquery
    client = bigquery.Client(project=project, credentials=creds)
    for name in TABLES:
        def inspect_table():
            table_id = f'{project}.{dataset}.{name}'
            table = client.get_table(table_id, timeout=30)
            audit.raw(name + '_before.json', table.to_api_repr())
            if table.table_type != 'TABLE':
                audit.check('bq_' + name, 'FAIL', 'Expected existing base table; preserved')
                return
            try:
                missing = schema_plan(table.schema)
            except ValueError as exc:
                audit.check('bq_' + name, 'FAIL', str(exc))
                return
            if missing and not verify_only:
                # Metadata patch uses the fetched etag. No SQL, loads, insertions, or row writes.
                table.schema = list(table.schema) + [bigquery.SchemaField(f, 'STRING', mode='NULLABLE') for f in missing]
                client.update_table(table, ['schema'], timeout=30)
            after = client.get_table(table_id, timeout=30)
            audit.raw(name + '_after.json', after.to_api_repr())
            remaining = schema_plan(after.schema)
            for field in after.schema:
                if field.name in FIELDS:
                    audit.schema.append(dict(table=name, field=field.name, type=field.field_type, mode=field.mode))
            audit.check('bq_' + name, 'FAIL' if remaining else 'PASS',
                        'Missing=' + ','.join(remaining) + '; verified metadata only; no historical backfill')
        audit.section('bq_' + name, inspect_table)


def sheets_checks(audit, creds, sheet_id, verify_only):
    import gspread
    client = gspread.authorize(creds)
    client.set_timeout(30)
    book = client.open_by_key(sheet_id)
    if book.title != 'OPTION_SHEET':
        audit.check('sheet_provenance', 'FAIL', 'Spreadsheet title mismatch; preserved')
        return
    try:
        ws = book.worksheet('WRITE_PROVENANCE')
    except gspread.WorksheetNotFound:
        if verify_only:
            audit.check('sheet_provenance', 'FAIL', 'WRITE_PROVENANCE missing')
            return
        ws = book.add_worksheet(title='WRITE_PROVENANCE', rows=2000, cols=6)
    values = ws.get_all_values()
    audit.raw('sheet_before.json', {'title': book.title, 'tab': ws.title,
              'headers': values[0] if values else [], 'existing_row_count': max(0, len(values)-1)})
    try:
        plan = sheet_plan(values)
    except ValueError as exc:
        audit.check('sheet_provenance', 'FAIL', str(exc))
        return
    if plan == 'initialize' and not verify_only:
        # Header only. Never append runtime events or clear existing rows.
        ws.update(range_name='A1:F1', values=[HEADERS], value_input_option='RAW')
    after = ws.row_values(1)
    audit.raw('sheet_after.json', {'headers': after})
    audit.check('sheet_provenance', 'PASS' if after == HEADERS else 'FAIL',
                'Header verified; no runtime rows created' if after == HEADERS else 'Headers missing')


def write_csv(path, rows, columns):
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        # Prevent spreadsheet formula execution when opening provider-controlled text.
        writer.writerows({k: "'" + str(v) if str(v).startswith(('=', '+', '-', '@')) else v
                          for k, v in row.items()} for row in rows)


def report(audit, mode):
    required = [c for c in audit.checks if c['status'] != 'NOT_PROVEN']
    ready = bool(required) and all(c['status'] == 'PASS' for c in required)
    result = dict(generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                  mode=mode, infrastructure='PASS' if ready else 'NOT_READY',
                  runtime='NOT_PROVEN', safety='NO_MARKET_RUN_NO_BROKER_CALLS_NO_RUNTIME_ROWS',
                  checks=audit.checks, schema=audit.schema, ci=audit.ci)
    audit.raw('operation_log.json', audit.checks)
    (audit.folder / 'SYSTEM_STATUS.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    write_csv(audit.folder / 'checks.csv', audit.checks, ['check', 'status', 'detail'])
    write_csv(audit.folder / 'bigquery_schema.csv', audit.schema, ['table', 'field', 'type', 'mode'])
    write_csv(audit.folder / 'symbols.csv', audit.symbols, ['symbol'])
    write_csv(audit.folder / 'ci.csv', audit.ci, ['id', 'head_sha', 'name', 'path', 'status', 'conclusion', 'html_url', 'created_at'])
    md = ['# Infrastructure readiness', '', 'Infrastructure: ' + result['infrastructure'],
          'Runtime: NOT_PROVEN', 'Mode: ' + mode, '',
          'No scanner run, workflow dispatch, broker call, or runtime row was performed.', '',
          '| Check | Status | Evidence |', '|---|---|---|']
    for c in audit.checks:
        md.append('| ' + ' | '.join(str(c[k]).replace('|', '\\|').replace('\n', ' ') for k in ('check', 'status', 'detail')) + ' |')
    (audit.folder / 'SYSTEM_STATUS.md').write_text('\n'.join(md), encoding='utf-8')
    rows = ''.join('<tr><td>' + html.escape(c['check']) + '</td><td class="' + c['status'] + '">' +
                   html.escape(c['status']) + '</td><td>' + html.escape(c['detail']) + '</td></tr>' for c in audit.checks)
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Infrastructure readiness evidence</title><style>body{font:16px system-ui;background:#101827;color:#e5ecf4;margin:30px;max-width:1400px}h1{font-size:30px}.card{padding:20px;background:#1d293c;border-radius:12px;margin:16px 0}table{border-collapse:collapse;width:100%}td,th{padding:12px;text-align:left;border-bottom:1px solid #40516a;overflow-wrap:anywhere}.PASS{color:#6de7af}.FAIL{color:#ff9494}.UNKNOWN,.NOT_PROVEN{color:#ffd580}a{color:#9dccff}</style>
<h1>Infrastructure readiness</h1><div class="card">Infrastructure: <strong>''' + result['infrastructure'] + '''</strong><br>Market runtime: <strong>NOT_PROVEN</strong><br>''' + html.escape(mode) + '''<br>''' + result['generated_at'] + '''</div>
<p>Metadata and configuration evidence only. No broker calls or runtime rows. Static writer checks do not prove deployed IAM or a cross-runtime lease.</p>
<p><a href="SYSTEM_STATUS.json">JSON</a> Â· <a href="SYSTEM_STATUS.md">Markdown</a> Â· <a href="checks.csv">Checks CSV</a> Â· <a href="bigquery_schema.csv">Schema CSV</a> Â· <a href="symbols.csv">Symbols CSV</a> Â· <a href="ci.csv">CI CSV</a> Â· <a href="raw/operation_log.json">Operation log</a></p>
<table><thead><tr><th>Check</th><th>Status</th><th>Evidence / next action</th></tr></thead><tbody>''' + rows + '</tbody></table></html>'
    (audit.folder / 'SYSTEM_STATUS.html').write_text(page, encoding='utf-8')
    hashes = [{'file': str(p.relative_to(audit.folder)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
              for p in sorted(audit.folder.rglob('*')) if p.is_file()]
    write_csv(audit.folder / 'SHA256SUMS.csv', hashes, ['file', 'sha256'])
    return 0 if ready else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--offline', action='store_true', help='Local checks only; cloud and CI marked UNKNOWN')
    args = parser.parse_args(argv)
    stamp = dt.datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y%m%d_%H%M%S_%f')
    folder = args.output_root / ('INFRA_READY_' + stamp)
    (folder / 'raw').mkdir(parents=True, exist_ok=False)
    audit = Audit(args.repo.resolve(), folder)
    audit.section('local_checks', lambda: local_checks(audit, args.offline))
    if args.offline:
        audit.check('exact_sha_ci', 'UNKNOWN', 'Offline')
        audit.check('bigquery', 'UNKNOWN', 'Offline')
        audit.check('sheet_provenance', 'UNKNOWN', 'Offline')
    else:
        audit.section('github', lambda: github_checks(audit))
        try:
            manifest = json.loads((audit.repo / 'agent_manifest.json').read_text(encoding='utf-8-sig'))
            resources = manifest['cloud_resources']
            creds = google_credentials(audit.repo)
        except Exception as exc:
            audit.check('google_credentials', 'UNKNOWN', type(exc).__name__ + '; credentials not logged')
        else:
            audit.section('bigquery', lambda: bigquery_checks(audit, creds, resources['gcp_project_id'],
                          resources['bigquery_dataset'], args.verify_only))
            audit.section('sheet_provenance', lambda: sheets_checks(audit, creds, resources['google_sheet_id'], args.verify_only))
    code = report(audit, 'OFFLINE' if args.offline else ('VERIFY_ONLY' if args.verify_only else 'PREPARE_METADATA_ONLY'))
    print('Evidence: ' + str(folder.resolve()))
    print('Open SYSTEM_STATUS.html. Exit 0 = infrastructure verified; 1 = failed/unknown checks; 2 = launcher failure.')
    return code


if __name__ == '__main__':
    sys.exit(main())

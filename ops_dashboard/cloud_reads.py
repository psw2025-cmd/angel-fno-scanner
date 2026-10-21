"""Bounded cloud access observations. Only metadata and tiny Sheet GETs; no SQL or writes."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys

def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def unknown(reason):
    return {name: {'source': name, 'health': 'UNKNOWN', 'freshness': 'UNKNOWN', 'collection': 'ERROR', 'observed_at': utc_now(), 'evidence': reason}
            for name in ('bigquery_live', 'google_sheets_live')}

def collect_cloud(repo):
    try:
        result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), str(repo)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=65)
        if result.returncode != 0:
            return unknown('Cloud worker failed; stderr withheld to protect credentials')
        data = json.loads(result.stdout)
        for name in ('bigquery_live', 'google_sheets_live'):
            item = data[name]
            age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(item['observed_at'])).total_seconds()
            if item.get('source') != name or item.get('health') not in ('PASS','FAIL','UNKNOWN') or not 0 <= age <= 120:
                return unknown('Invalid, stale or future cloud-worker observation')
        return data
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
        return unknown('Cloud worker timed out, unavailable or returned invalid evidence')

def observe(name, action):
    started = utc_now()
    try:
        details = action()
        return {'source': name, 'health':'PASS', 'collection':'OK', 'freshness':'FRESH', 'started_at':started,
                'observed_at':utc_now(), 'evidence':'Authenticated read-only API access; not data parity, market freshness or trading readiness', **details}
    except Exception as exc:
        code = getattr(getattr(exc, 'response', None), 'status_code', None)
        return {'source':name, 'health':'FAIL' if code in (401,403,404) else 'UNKNOWN', 'collection':'ERROR',
                'freshness':'UNKNOWN', 'started_at':started, 'observed_at':utc_now(), 'error_type':type(exc).__name__,
                'http_status':code, 'evidence':'Authenticated cloud read failed; no historical success substituted'}

def worker(repo):
    sys.path.insert(0, str(repo))
    from credentials import load_env, resolve_service_account_info
    import google.auth
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    from urllib.parse import quote
    load_env()
    manifest = json.loads((repo / 'agent_manifest.json').read_text(encoding='utf-8-sig'))
    resources = manifest['cloud_resources']
    if resources['gcp_project_id'] != 'fno-angel-prod-1790444589':
        raise ValueError('Unexpected project')
    scopes = ['https://www.googleapis.com/auth/bigquery.readonly', 'https://www.googleapis.com/auth/spreadsheets.readonly']
    info = resolve_service_account_info()
    creds = service_account.Credentials.from_service_account_info(info, scopes=scopes) if info else google.auth.default(scopes=scopes)[0]
    session = AuthorizedSession(creds)
    # No POST, PATCH, PUT, DELETE, SQL, load or broker operations are implemented.
    def read(url, params=None):
        response = session.get(url, params=params, timeout=12)
        response.raise_for_status()
        return response.json()
    def bigquery():
        project = resources['gcp_project_id']
        dataset = resources['bigquery_dataset']
        table = read('https://bigquery.googleapis.com/bigquery/v2/projects/' + quote(project,safe='') + '/datasets/' + quote(dataset,safe='') + '/tables/option_predictions_live')
        if table.get('tableReference',{}).get('projectId') != project or table.get('tableReference',{}).get('tableId') != 'option_predictions_live':
            raise ValueError('Wrong table readback')
        return {'project':project, 'table':'option_predictions_live', 'rows_metadata':table.get('numRows'),
                'last_modified_epoch_ms':table.get('lastModifiedTime'), 'metadata_only':True, 'query_executed':False}
    def sheets():
        sheet_id = resources['google_sheet_id']
        base = 'https://sheets.googleapis.com/v4/spreadsheets/' + quote(sheet_id,safe='')
        meta = read(base, {'fields':'spreadsheetId,sheets.properties(sheetId,title)'})
        if meta.get('spreadsheetId') != sheet_id or not meta.get('sheets'):
            raise ValueError('Missing or wrong spreadsheet readback')
        titles = [s['properties']['title'] for s in meta['sheets']]
        title = 'HEARTBEAT' if 'HEARTBEAT' in titles else titles[0]
        selected = "'" + title.replace("'", "''") + "'!A1:C2"
        values = read(base + '/values/' + quote(selected,safe=''), {'valueRenderOption':'FORMATTED_VALUE'})
        grid = values.get('values',[])
        return {'spreadsheet_id':sheet_id, 'tab_count':len(titles), 'sample_range':selected,
                'returned_rows':len(grid), 'sample_sha256':hashlib.sha256(json.dumps(grid,sort_keys=True).encode()).hexdigest(),
                'sample_values_exported':False, 'parity_verified':False}
    return {'bigquery_live':observe('bigquery_live',bigquery), 'google_sheets_live':observe('google_sheets_live',sheets)}

if __name__ == '__main__':
    try:
        print(json.dumps(worker(Path(sys.argv[1]))))
    except Exception as exc:
        print(json.dumps(unknown('Credential/dependency setup failed: ' + type(exc).__name__)))

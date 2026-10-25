"""Read-only publication prerequisite probes; never invoke a production writer."""
import argparse
import contextlib
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--stage', choices=['broker', 'universe', 'sheets', 'bigquery', 'current', 'export'], required=True)
    a = p.parse_args()
    from market_calendar import market_session_state
    result = {'run_id': uuid.uuid4().hex, 'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'stage': a.stage, 'market': market_session_state(), 'scope': 'read-only prerequisite observation; no publication cycle'}
    os.environ['ALLOW_PRODUCTION_WRITES'] = '0'
    subjects = ['angel_prediction_engine.py', 'publication.py', 'agent_cli.py', 'agent_manifest.json',
                'credentials.py', 'tools/check_freshness.py', 'tools/atomic_snapshots.py', 'tools/publication_gap_probe.py']
    result['sha256'] = {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in subjects}
    try:
        # Third-party broker logs may contain authentication payloads. Do not retain them.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import angel_prediction_engine as e
            if a.stage in ('broker', 'universe'):
                if a.stage == 'broker':
                    result['last_operation'] = 'get_angel_client'
                    api = e.get_angel_client()
                    result['login_accepted'] = True
                result['last_operation'] = 'instrument_discovery'
                master = e.load_or_download_scrip_master()
                cache = Path(e.SCRIP_CACHE_PATH)
                result['instrument_input'] = {'cache_exists': cache.is_file(), 'records': len(master),
                    'sha256': hashlib.sha256(json.dumps(master,sort_keys=True).encode()).hexdigest()}
                result['related_instruments'] = sorted({(str(c.get('name')), str(c.get('instrumenttype')), str(c.get('expiry')))
                    for c in master if str(c.get('name','')).startswith('ICICIPRU') and c.get('exch_seg')=='NFO'})
                discovered = e.discover_fno_universe(master)
                from universe_contract import verified_symbols
                result['discovered_universe'] = len(discovered)
                result['missing_manifest_symbols'] = sorted(set(verified_symbols())-set(discovered))
                result['unreviewed_discovered_symbols'] = sorted(set(discovered)-set(verified_symbols()))
                universe = e.select_verified_universe(discovered)
                if a.stage == 'broker':
                    result['last_operation'] = 'futures_quotes'
                    quotes = e.fetch_quotes_in_batches(api, [v['fut_token'] for v in universe.values()], chunk_size=45)
                    missing = [s for s,v in universe.items() if float(quotes.get(v['fut_token'], {}).get('ltp', 0)) <= 0]
                    result.update(verified_universe=len(universe), missing_positive_futures=len(missing))
                    if missing:
                        raise ValueError('Missing positive futures quotes')
            elif a.stage == 'sheets':
                sh = e.get_gspread_client().open_by_key(e.require_authoritative_sheet_id(e.SHEET_ID))
                titles = [w.title for w in sh.worksheets()]
                result['tabs'] = titles
                result['missing_required'] = sorted(set(['FORENSIC_LIVE','HEARTBEAT','NEWS_LIVE'])-set(titles))
                if result['missing_required']:
                    raise ValueError('Required tabs missing')
            elif a.stage == 'bigquery':
                client = e.get_bigquery_client()
                from tools.schema_validator import load_schema
                from tools.live_schema_guard import assert_truncate_schema_safe
                result['tables'] = {}
                for name in ['option_predictions_live','market_news_sentiment','prediction_calibration_log','next_day_gap_predictions']:
                    table = client.get_table(client.dataset(e.BQ_DATASET_ID).table(name))
                    result['tables'][name] = {'schema_fields': len(table.schema)}
                    if name == 'option_predictions_live':
                        schema = load_schema(name)
                        assert_truncate_schema_safe(schema, table.schema, load_fields=schema, autodetect=False)
            elif a.stage == 'current':
                from publication import verify_current_publication
                sh = e.get_gspread_client().open_by_key(e.require_authoritative_sheet_id(e.SHEET_ID))
                client = e.get_bigquery_client()
                result['identity'] = verify_current_publication(sh, client, client.dataset(e.BQ_DATASET_ID).table('option_predictions_live'))
            elif a.stage == 'export':
                path = os.getenv('ANGEL_CYCLE_METADATA_FILE')
                result['metadata_configured'] = bool(path)
                if not path:
                    raise ValueError('ANGEL_CYCLE_METADATA_FILE missing; snapshot export blocked')
                meta = json.loads(Path(path).read_text(encoding='utf-8'))
                if meta.get('data_freshness_status') != 'EXCHANGE_VERIFIED':
                    raise ValueError('cycle metadata not exchange verified')
                from tools.check_freshness import validate
                result['freshness'] = validate(meta.get('source_timestamp'),meta.get('run_id'),meta.get('git_sha'),meta.get('cycle_id'),meta.get('market_session'),expected=meta)
        result['status'] = 'PASS'
    except Exception as exc:
        result['status'] = 'BLOCKED'
        result['error_type'] = type(exc).__name__
        if a.stage == 'broker' and str(exc).startswith('Angel One session rejected: '):
            import ast
            try:
                payload = ast.literal_eval(str(exc).split(': ', 1)[1])
                if isinstance(payload, dict):
                    code = str(payload.get('errorcode', ''))
                    result['broker_error_code'] = code if code.isalnum() else 'UNCLASSIFIED'
                    result['broker_status'] = payload.get('status') is True
            except (ValueError, SyntaxError):
                pass
        # Fixed descriptions prevent tokens and server-returned auth data leaking.
        result['reason'] = {'broker':'Broker login, instrument discovery, or positive futures coverage failed',
                            'universe':'Instrument discovery does not satisfy the reviewed universe',
                            'sheets':'Sheet listing or required tabs unavailable',
                            'bigquery':'Table metadata or truncate-schema compatibility unavailable',
                            'current':'Current publication marker/readback could not be verified',
                            'export':'Exchange-verified cycle metadata missing, invalid, or stale'}[a.stage]
    result['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    result['exit_code'] = 0 if result['status'] == 'PASS' else 1
    target = ROOT/'audit'/'publication-gap'/result['run_id']
    target.mkdir(parents=True)
    (target/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    print('Receipt: '+str(target/'receipt.json'))
    return result['exit_code']

if __name__ == '__main__':
    raise SystemExit(main())

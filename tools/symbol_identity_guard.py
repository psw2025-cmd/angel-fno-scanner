#!/usr/bin/env python3
"""Read-only symbol identity guard. Standard library only."""
import argparse, datetime as dt, hashlib, json, os, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTRY = ROOT / 'config' / 'corporate_action_registry.json'
TARGETS = [ROOT / 'agent_manifest.json', ROOT / 'config' / 'fno_canonical_universe_219.json']

def load(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def lists(obj, path='$'):
    if isinstance(obj, list):
        if obj and all(isinstance(v, str) for v in obj):
            yield path, obj
        for i, v in enumerate(obj): yield from lists(v, f'{path}[{i}]')
    elif isinstance(obj, dict):
        for k, v in obj.items(): yield from lists(v, f'{path}.{k}')

def symbol_at(old, when, registry):
    for event in sorted(registry['events'], key=lambda e:e['effective_date']):
        if event['old_symbol'] == old and when >= event['effective_date'] and event['status'] == 'exchange_verified':
            old = event['new_symbol']
    return old

def audit():
    results=[]
    def record(name,status,detail): results.append({'check':name,'status':status,'detail':detail})
    try:
        registry=load(REGISTRY)
        assert registry['schema_version']==1
        assert isinstance(registry['events'],list)
        for e in registry['events']:
            assert dt.date.fromisoformat(e['effective_date'])
            assert all(e.get(k) for k in ('old_symbol','new_symbol','source_url','source_ref','status'))
            assert e['old_symbol'] != e['new_symbol']
            assert e['status'] in ('exchange_verified','pending_review','rejected')
        record('REGISTRY_SCHEMA','PASS',f'{len(registry["events"])} events')
    except Exception as exc:
        record('REGISTRY_SCHEMA','FAIL',str(exc)); registry={'events':[]}
    today=dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=5,minutes=30))).date().isoformat()
    sets=[]
    for path in TARGETS:
        try:
            obj=load(path)
            matches=[(p,s) for p,s in lists(obj) if 'ICICILIFE' in s or 'ICICIPRULI' in s]
            valid=[(p,s) for p,s in matches if len(s)==219 and len(set(s))==219]
            if len(valid) != 1:
                record(path.name,'FAIL',f'Expected exactly one 219-unique-symbol list containing ICICI identity, found {len(valid)}; candidate lists {len(matches)}')
            else:
                p,s=valid[0]
                expected=symbol_at('ICICIPRULI',today,registry)
                ok=expected in s and ('ICICIPRULI' not in s if expected=='ICICILIFE' else 'ICICILIFE' not in s)
                record(path.name,'PASS' if ok else 'FAIL',f'{p}: count={len(s)} unique={len(set(s))} expected={expected}')
                sets.append((path.name,set(s)))
        except Exception as exc:
            record(path.name,'FAIL',str(exc))
    if len(sets)==2:
        record('UNIVERSE_AGREEMENT','PASS' if sets[0][1]==sets[1][1] else 'FAIL',f'symmetric_difference={sorted(sets[0][1]^sets[1][1])}')
    else: record('UNIVERSE_AGREEMENT','BLOCKED','Two comparable 219-symbol lists not confirmed')
    testdates=[('2026-10-22','ICICIPRULI'),('2026-10-23','ICICILIFE'),('2026-10-26','ICICILIFE')]
    for date,expected in testdates:
        resolved=symbol_at('ICICIPRULI',date,registry)
        record('DATE_ALIAS_'+date,'PASS' if resolved==expected else 'FAIL',f'actual={resolved}, expected={expected}')
    # No broker credentials or external data are read by this offline checker.
    record('BROKER_INSTRUMENT_IDENTITY','BLOCKED','Live authenticated broker-master check required')
    record('DOWNSTREAM_BIGQUERY_SHEETS_POWERBI','BLOCKED','Authenticated sink readbacks required')
    record('END_TO_END_PRODUCTION','BLOCKED','Valid market-cycle receipts, CI, source and sink lineage required')
    out={'checked_at_ist':dt.datetime.now(dt.timezone(dt.timedelta(hours=5,minutes=30))).isoformat(),
         'mode':'READ_ONLY_OFFLINE','results':results,
         'offline_status':'FAIL' if any(x['status']=='FAIL' for x in results) else 'PASS',
         'production_certified':False}
    proof=ROOT/'proof-output'/'symbol-identity'
    proof.mkdir(parents=True,exist_ok=True)
    (proof/'identity_audit.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    for x in results: print(f'{x["status"]:7} {x["check"]}: {x["detail"]}')
    print('Report:',proof/'identity_audit.json')
    return 1 if out['offline_status']=='FAIL' else 0

if __name__=='__main__': sys.exit(audit())

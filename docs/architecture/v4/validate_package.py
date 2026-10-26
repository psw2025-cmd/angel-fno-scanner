"""Offline design-archive integrity validator. NOT a runtime/cloud certification."""
from pathlib import Path
import hashlib, json, sys, zipfile
root=Path(__file__).resolve().parent
manifest=json.loads((root/'14_FILE_MANIFEST.json').read_text(encoding='utf-8'))
errors=[]
for x in manifest['files']:
    p=root/x['path']
    if not p.is_file(): errors.append('MISSING '+x['path']); continue
    got=hashlib.sha256(p.read_bytes()).hexdigest()
    if got != x['sha256']: errors.append('HASH_MISMATCH '+x['path'])
for name in ('04_MACHINE_READABLE_STATUS_TEMPLATE.json','08_MANIFEST_SHA256.json','14_FILE_MANIFEST.json'):
    try: json.loads((root/name).read_text(encoding='utf-8'))
    except Exception as e: errors.append('INVALID_JSON '+name+': '+str(e))
required=('09_PREHANDOFF_GAP_CLOSURE_V4.md','10_AGENT_HANDOFF_PROTOCOL_V4.md','11_OWNER_OUTCOME_AND_METRIC_CONTRACT.md','12_SOURCE_AND_PERMISSION_REGISTER.csv','13_HARD_STOP_ACCEPTANCE.csv')
for name in required:
    if not (root/name).exists(): errors.append('MISSING '+name)
print(json.dumps({'scope':'DESIGN_ARCHIVE_ONLY','files_checked':len(manifest['files']),'status':'FAIL' if errors else 'PASS','errors':errors},indent=2))
sys.exit(bool(errors))

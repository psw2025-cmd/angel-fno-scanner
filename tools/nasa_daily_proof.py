#!/usr/bin/env python3
import json,pathlib,subprocess,os,datetime,re
root=pathlib.Path(__file__).resolve().parents[1]
data=json.loads((root/'docs/PROVEN_PROOF_LEDGER.json').read_text())
stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
sha=os.getenv('GITHUB_SHA','')
def run(args,timeout=120):
 try:
  p=subprocess.run(args,cwd=root,capture_output=True,text=True,timeout=timeout)
  return p.returncode,(p.stdout+'\n'+p.stderr)[-2000:]
 except Exception as e: return -1,str(e)
for c in data['checks']:
 n=c['id']; status='BLOCKED';detail='External cloud/local credentials or measurable evidence unavailable'
 if n==1:
  p=root/'n8n-workflows'
  if p.exists():
   hits=[str(f.relative_to(root)) for f in p.rglob('*.json') if any(s in f.read_text(errors='replace') for s in ('C:/AngelFNO_Workstation','127.0.0.1','localhost:5680','localhost:8080','/mnt/c/'))]
   status='PASS' if not hits else 'FAIL';detail={'matching_files':hits}
  else: detail='No n8n-workflows directory'
 elif n==2:
  p=root/'n8n-workflows';count=len([f for f in p.glob('*.json') if f.name!='manifest.json']) if p.exists() else 0
  status='PASS' if count==17 else 'FAIL';detail={'workflow_json_count':count,'caveat':'count does not prove semantic parity'}
 elif n==5:
  p=root/'tools/memory_guard.py'
  if p.exists():
   code,out=run(['python',str(p)],60);status='PASS' if code==0 and re.search(r'\b6\b',out) else 'FAIL';detail={'exit_code':code,'output':out}
 elif n==6:
  code,out=run(['python','-m','pytest','-q'],180);m=re.search(r'(\d+) passed',out)
  status='PASS' if code==0 and m and int(m.group(1))>=221 else 'FAIL';detail={'exit_code':code,'output':out}
 elif n==4: detail='Full 64-hex checksum and canonical 219-symbol artifact must be verified, not just a prefix'
 elif n==9: detail='Filename grep cannot prove absence of plaintext secrets; run credential-safe secret scanner and Git history scan'
 elif n==14: detail='Cloud IAM deny proof requires deployed principal and real permission denial, not just pytest'
 c.update(status=status,observed_at_utc=stamp,source_sha=sha,evidence=detail)
data['last_ci_observation_utc']=stamp
data['summary']={s:sum(c['status']==s for c in data['checks']) for s in ('PASS','FAIL','BLOCKED','NOT_RUN')}
out=root/'proof-output';out.mkdir(exist_ok=True)
(out/'PROVEN_PROOF_LEDGER.json').write_text(json.dumps(data,indent=2)+'\n')
print(data['summary'])

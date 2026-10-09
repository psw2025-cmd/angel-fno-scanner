from pathlib import Path
import subprocess,json,sys,os,datetime
root=Path(__file__).resolve().parents[1]
outdir=root/"proof-output";outdir.mkdir(exist_ok=True)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
result={"timestamp_utc":now,"source_sha":os.getenv("GITHUB_SHA"),"checks":[]}
def check(name,cmd,timeout=90):
 try:
  p=subprocess.run(cmd,cwd=root,capture_output=True,timeout=timeout,env={**os.environ,"LIVE_TRADING_ENABLED":"false"})
  stdout=p.stdout.decode("utf-8","replace")
  stderr=p.stderr.decode("utf-8","replace")
  return p.returncode,stdout,stderr
 except Exception as e:return -99,"",type(e).__name__
rc,helpout,helpe=check("help",[sys.executable,"agent_cli.py","--help"],40)
registered=rc==0 and "--json-only" in helpout
result["checks"].append({"name":"CLI registration","status":"PASS" if registered else "FAIL","exit_code":rc,"reason":"flag visible in --help" if registered else "missing registration or import error"})
if registered:
 rc,stdout,stderr=check("purity",[sys.executable,"agent_cli.py","--verify","--json-only"],90)
 try:
  data=json.loads(stdout)
  pure=True
 except (ValueError,TypeError):
  pure=False
 result["checks"].append({"name":"JSON-only purity","status":"PASS" if pure and rc in (0,1) else "FAIL","exit_code":rc,"stdout_json":pure,"stderr_present":bool(stderr),"classification":"AUDIT_FAIL" if rc==1 and pure else "CLI_BROKEN" if rc==2 else "RUNTIME_OR_JSON_FAILURE" if not pure else "AUDIT_PASS"})
else:
 result["checks"].append({"name":"JSON-only purity","status":"BLOCKED","reason":"CLI registration failed"})
(outdir/"cli_forensic_gate.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result,indent=2))
sys.exit(0 if all(c["status"]=="PASS" for c in result["checks"]) else 1)

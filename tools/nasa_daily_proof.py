#!/usr/bin/env python3
"""Read-only evidence collector; writes a timestamped JSON artifact, never fakes cloud PASS."""
import argparse, datetime, hashlib, json, os, pathlib, re, subprocess, sys, urllib.request
R=pathlib.Path(__file__).resolve().parents[1]
def cmd(argv,timeout=50):
    try:
        p=subprocess.run(argv,cwd=R,capture_output=True,text=True,errors="replace",timeout=timeout,env={**os.environ,"LIVE_TRADING_ENABLED":"false","PYTHONIOENCODING":"utf-8"})
        return p.returncode,(p.stdout or "")[-4000:],(p.stderr or "")[-800:]
    except Exception as e:return -1,"",str(e)
def scan_emoji(s):
    return bool(re.search("[\U0001F300-\U0001FAFF\u2600-\u27BF]",s))
def run():
    data=json.loads((R/"docs/PROVEN_PROOF_LEDGER.json").read_text(encoding="utf-8"))
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    sha=os.environ.get("GITHUB_SHA") or cmd(["git","rev-parse","HEAD"])[1].strip()
    report={}
    def record(n,status,reason,proof=None):
        report[n]=(status,reason,proof)
    # Compile explicitly with UTF-8 and CP1252 fallback; do not edit source.
    src=R/"verify_all_sheets_and_engine.py"
    if src.exists():
        b=src.read_bytes()
        try:
            compile(b.decode("utf-8"),str(src),"exec")
            print("SOURCE_COMPILE utf-8 PASS")
        except UnicodeDecodeError:
            try:
                compile(b.decode("cp1252"),str(src),"exec")
                print("SOURCE_COMPILE cp1252 PASS (portability warning)")
            except Exception as e:
                print("SOURCE_COMPILE FAIL",type(e).__name__)
        except Exception as e:print("SOURCE_COMPILE FAIL",type(e).__name__)
    else:print("SOURCE_COMPILE BLOCKED missing file")
    # 1: inspect tracked Python print statements for emoji; static source only
    tracked=cmd(["git","ls-files","*.py"])[1].splitlines()
    bad=[]
    for rel in tracked:
        p=R/rel
        if p.is_file():
            for i,line in enumerate(p.read_text(encoding="utf-8",errors="replace").splitlines(),1):
                if "print(" in line and scan_emoji(line):bad.append(f"{rel}:{i}")
    record(1,"FAIL" if bad else "PASS","Static tracked-Python print emoji scan",{"matches":bad[:30],"scanned_files":len(tracked)})
    # 2: untracked and modified files on runner are not the user's laptop orphans
    c,out,err=cmd(["git","status","--porcelain","--untracked-files=normal"])
    orphans=[x for x in out.splitlines() if x.startswith("??")]
    record(2,"PASS" if c==0 and len(orphans)<10 else "FAIL","Runner checkout only, not local workstation",{"untracked":len(orphans),"changed_total":len(out.splitlines())})
    # 3: ignored harness files must be counted via glob
    harness=list((R/"audit").glob("verify_harness_*.json")) if (R/"audit").exists() else []
    record(3,"PASS" if len(harness)<20 else "FAIL","Runner checkout only; ignored local files absent",{"harness":len(harness)})
    # 4: check tracked desktop.ini and current workspace
    tracked_ini=[x for x in cmd(["git","ls-files"])[1].splitlines() if x.lower().endswith("/desktop.ini") or x.lower()=="desktop.ini"]
    record(4,"PASS" if not tracked_ini else "FAIL","Tracked files only; ignored workstation desktop.ini may still exist",{"tracked_desktop_ini":tracked_ini})
    # 5,6: external data and canonical full digest require explicit evidence
    for n in (5,6):record(n,"BLOCKED","Requires authenticated source readback and canonical full SHA-256 artifact")
    # 7: full pytest may be slow; don't claim 221 unless reproduced
    if os.getenv("NASA_RUN_PYTEST","1")=="1":
        c,out,err=cmd([sys.executable,"-m","pytest","-q"],timeout=300)
        m=re.search(r"(\d+)\s+passed",out)
        record(7,"PASS" if c==0 and m and int(m.group(1))>=221 else "FAIL","Exact observed pytest count; historical 221 is not guaranteed",{"exit":c,"passed":int(m.group(1)) if m else None,"tail":(out+err)[-650:]})
    else:record(7,"BLOCKED","Full pytest disabled by environment")
    # 8: six-file guard requires actual six-file evidence
    mg=R/"tools/memory_guard.py"
    if mg.exists():
        c,out,err=cmd([sys.executable,str(mg)],90)
        record(8,"PASS" if c==0 and re.search(r"\b6\b",out) else "FAIL","Requires 6-file proof in output",{"exit":c,"tail":(out+err)[-700:]})
    else:record(8,"BLOCKED","tools/memory_guard.py absent")
    # 9,10: do not mistake hosted runner for laptop
    url=os.getenv("N8N_HEALTH_URL","")
    if url and url.startswith("https://"):
        try:
            with urllib.request.urlopen(url,timeout=8) as res:
                record(9,"PASS" if res.status==200 else "FAIL","Configured HTTPS endpoint",{"status_code":res.status})
        except Exception as e:record(9,"FAIL","Configured HTTPS endpoint unavailable",type(e).__name__)
    else:record(9,"BLOCKED","No externally accessible N8N_HEALTH_URL; localhost runner is not laptop")
    record(10,"BLOCKED","Canonical N8N_USER_FOLDER must be read from actual n8n service environment")
    # 11: filename scan is not a credential content/history audit
    record(11,"BLOCKED","Requires secret scanning tracked content, artifacts and Git history; filename grep insufficient")
    for n,why in [(12,"Signed authenticated cloud /version endpoint unavailable"),(13,"Lease fencing and BQ commit marker unavailable"),(14,"Actual cold restore and encryption key recovery not executed"),(15,"Live n8n API desired-vs-observed active flags unavailable"),(16,"Cloud principal IAM-deny integration test unavailable"),(17,"Billing budget/quota access and alert drill unavailable")]:
        record(n,"BLOCKED",why)
    # 18: run 3 independent read-only CLI verifications only when explicitly enabled with credentials
    if os.getenv("NASA_ENABLE_CLOUD_VERIFY","0")=="1" and (R/"agent_cli.py").exists():
        outputs=[]
        for i in range(1,4):
            c,out,err=cmd([sys.executable,"agent_cli.py","--verify","--format","json"],timeout=120)
            p=R/"proof-output"/f"verify_{i}.json"
            p.parent.mkdir(exist_ok=True)
            # Never persist raw cloud response: may contain sensitive account data.
            try:
                j=json.loads(out)
                digest=hashlib.sha256(json.dumps(j,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
                outputs.append({"iteration":i,"exit":c,"json":True,"sha256":digest})
            except Exception:outputs.append({"iteration":i,"exit":c,"json":False,"error_type":"non_json_or_mixed_output"})
        good=all(x["exit"]==0 and x["json"] for x in outputs)
        same=good and len({x["sha256"] for x in outputs})==1
        record(18,"PASS" if same else "FAIL","Strict byte-normalized equality; time-varying fields may require semantic comparison",outputs)
    else:record(18,"BLOCKED","Set NASA_ENABLE_CLOUD_VERIFY=1 with scoped cloud credentials to run three verifications")
    # 19/20: Git worktrees and branches on checkout runner, not original workstation
    c,out,err=cmd(["git","worktree","list","--porcelain"])
    count=sum(x.startswith("worktree ") for x in out.splitlines())
    record(19,"PASS" if c==0 and count<=1 else "FAIL","Runner-only count; multiple legitimate local worktrees need not be defects",{"count":count})
    c,out,err=cmd(["git","branch","-r"])
    branches=[x.strip() for x in out.splitlines() if x.strip() and "->" not in x]
    record(20,"PASS" if c==0 and len(branches)<=5 else "FAIL","Remote branch count; threshold is policy, not intrinsic correctness",{"count":len(branches)})
    for item in data["checks"]:
        n=int(item["id"].split("-")[-1])
        status,reason,proof=report[n]
        item.update(status=status,timestamp=now,source_sha=sha,evidence={"reason":reason,"details":proof})
    data["generated_at_utc"]=now
    data["summary"]={s:sum(x["status"]==s for x in data["checks"]) for s in ("PASS","FAIL","BLOCKED","NOT_RUN")}
    target=R/"proof-output";target.mkdir(exist_ok=True)
    (target/"PROVEN_PROOF_LEDGER.json").write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("PROOF_SUMMARY",json.dumps(data["summary"],sort_keys=True))
    return 0
if __name__=="__main__":sys.exit(run())

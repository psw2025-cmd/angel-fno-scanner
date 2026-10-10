import json
from tools.orphan_reaper import classify_processes,write_audit

def test_only_scoped_old_processes(tmp_path):
    root=tmp_path/"owned"
    processes=[
        {"pid":3,"executable":str(root/"python.exe"),"created":1,"command":"python universal_supervisor.py"},
        {"pid":4,"executable":str(tmp_path/"other"/"python.exe"),"created":1,"command":"python universal_supervisor.py"},
        {"pid":5,"executable":str(root/"python.exe"),"created":99,"command":"python universal_supervisor.py"},
    ]
    decisions=classify_processes(processes,owner_pid=1,allow_root=root,now=100,min_age=10)
    assert [d["candidate"] for d in decisions]==[True,False,False]
    assert all(d["action"]!="KILL" for d in decisions)
    write_audit(tmp_path/"audit.jsonl",decisions)
    assert len(json.loads((tmp_path/"audit.jsonl").read_text())["decisions"])==3

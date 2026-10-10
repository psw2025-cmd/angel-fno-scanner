"""Conservative orphan inspection: no process termination without ownership proof."""
import json
import os
import time
from pathlib import Path

def classify_processes(processes, *, owner_pid, allow_root, now=None, min_age=900):
    """Classify only processes with matching executable path and declared supervisor root."""
    now=time.time() if now is None else now
    root=os.path.normcase(os.path.abspath(str(allow_root)))
    decisions=[]
    for proc in processes:
        pid=proc.get("pid")
        executable=proc.get("executable") or ""
        started=proc.get("created")
        command=proc.get("command") or ""
        candidate=(isinstance(pid,int) and pid>0 and pid!=owner_pid and
                   isinstance(started,(int,float)) and now-started>=min_age and
                   os.path.normcase(os.path.abspath(executable)).startswith(root+os.sep) and
                   "universal_supervisor.py" in command)
        decisions.append({"pid":pid,"candidate":bool(candidate),
                          "action":"INSPECT_ONLY" if candidate else "IGNORE"})
    return decisions

def write_audit(path,decisions):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as out:
        out.write(json.dumps({"ts":time.time(),"decisions":decisions},sort_keys=True)+"\n")
        out.flush()
        os.fsync(out.fileno())

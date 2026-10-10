"""Bounded local metrics counters with atomic snapshot output."""
import json
import os
import threading
from pathlib import Path

class Metrics:
    def __init__(self):
        self._lock=threading.Lock()
        self._counters={}

    def increment(self,name,amount=1):
        if not isinstance(name,str) or not name or amount<0:
            raise ValueError("invalid metric")
        with self._lock:
            self._counters[name]=self._counters.get(name,0)+amount

    def snapshot(self):
        with self._lock:
            return dict(self._counters)

    def write(self,path):
        path=Path(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_name(path.name+".tmp")
        tmp.write_text(json.dumps(self.snapshot(),sort_keys=True),encoding="utf-8")
        os.replace(tmp,path)

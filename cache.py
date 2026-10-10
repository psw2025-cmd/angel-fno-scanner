"""Bounded monotonic TTL cache; callers must choose freshness policy."""
from collections import OrderedDict
import threading
import time

class TTLCache:
    def __init__(self, ttl=60, maxsize=128, clock=time.monotonic):
        if ttl<=0 or maxsize<1: raise ValueError("invalid cache configuration")
        self.ttl=ttl
        self.maxsize=maxsize
        self.clock=clock
        self.items=OrderedDict()
        self.lock=threading.RLock()

    def get(self,key,default=None):
        with self.lock:
            entry=self.items.get(key)
            if entry is None: return default
            expires,value=entry
            if self.clock()>=expires:
                del self.items[key]
                return default
            self.items.move_to_end(key)
            return value

    def put(self,key,value):
        with self.lock:
            self.items[key]=(self.clock()+self.ttl,value)
            self.items.move_to_end(key)
            while len(self.items)>self.maxsize:
                self.items.popitem(last=False)

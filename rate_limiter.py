"""Thread-safe token bucket for a specifically configured upstream API."""
import threading
import time

class RateLimiter:
    def __init__(self, rate=3, capacity=6, clock=time.monotonic):
        if rate<=0 or capacity<1: raise ValueError("invalid limiter settings")
        self.rate=float(rate)
        self.capacity=float(capacity)
        self.tokens=float(capacity)
        self.clock=clock
        self.last=clock()
        self.lock=threading.Lock()

    def acquire(self, cost=1):
        if cost<=0 or cost>self.capacity: raise ValueError("invalid cost")
        with self.lock:
            now=self.clock()
            elapsed=max(0,now-self.last)
            self.tokens=min(self.capacity,self.tokens+elapsed*self.rate)
            self.last=now
            if self.tokens>=cost:
                self.tokens-=cost
                return 0.0
            return (cost-self.tokens)/self.rate

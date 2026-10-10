"""Minimal single-probe circuit breaker for isolated dependencies."""
import threading
import time

class CircuitOpen(RuntimeError): pass

class CircuitBreaker:
    def __init__(self, threshold=5, cooldown=60, clock=time.monotonic):
        if threshold<1 or cooldown<=0: raise ValueError("invalid breaker")
        self.threshold=threshold
        self.cooldown=cooldown
        self.clock=clock
        self.failures=0
        self.opened_at=None
        self.probe_in_flight=False
        self.lock=threading.Lock()

    def allow(self):
        with self.lock:
            if self.opened_at is None: return True
            if self.clock()-self.opened_at<self.cooldown: return False
            if self.probe_in_flight: return False
            self.probe_in_flight=True
            return True

    def success(self):
        with self.lock:
            self.failures=0
            self.opened_at=None
            self.probe_in_flight=False

    def failure(self):
        with self.lock:
            self.failures+=1
            if self.failures>=self.threshold:
                self.opened_at=self.clock()
            self.probe_in_flight=False

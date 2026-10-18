import threading, time
from dataclasses import dataclass, field

@dataclass
class BlockedEvent:
    at: float
    url: str
    host: str
    resource_type: str
    reason: str
    page_url: str
    stripped: list = field(default_factory=list)
    kind: str = "block"

class BlockedRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._events = []
        self._cursor = 0
    def add(self, e):
        with self._lock:
            self._events.append(e)
            if len(self._events) > 5000:
                del self._events[:1000]
    def drain(self):
        with self._lock:
            new = self._events[self._cursor:]
            self._cursor = len(self._events)
            return list(new)
    def snapshot(self):
        with self._lock:
            return list(self._events)
    def clear(self):
        with self._lock:
            self._events.clear()
            self._cursor = 0
    @staticmethod
    def now():
        return time.time()

import time
from collections import defaultdict, deque
from threading import Lock

class InMemoryRateLimiter:
    def __init__(self, max_requests, window_seconds):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)
        self.lock = Lock()

    def allow(self, key):
        now = time.time()
        cutoff = now - self.window_seconds
        with self.lock:
            bucket = self.requests[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                return False
            bucket.append(now)
            return True

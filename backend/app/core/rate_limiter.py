"""
In-process token bucket rate limiter. Pure logic (takes a clock function as
a parameter instead of calling time.time() directly), so it's fully
testable offline without sleeping in real tests.

For a single backend instance this is sufficient; for horizontal scaling
across multiple instances, back it with Redis (INCR + EXPIRE per window)
instead -- the interface (`allow(key) -> bool`) stays the same, so
middleware.py wouldn't need to change, only the store implementation.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class TokenBucketLimiter:
    def __init__(self, capacity: int, refill_per_second: float, clock=time.monotonic):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_per_second <= 0:
            raise ValueError("refill_per_second must be positive")
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}

    def allow(self, key: str, cost: float = 1.0) -> bool:
        """Returns True and consumes `cost` tokens if the bucket for `key`
        has enough; returns False (and consumes nothing) otherwise."""
        now = self._clock()
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(tokens=float(self.capacity), last_refill=now)
            self._buckets[key] = bucket

        elapsed = max(0.0, now - bucket.last_refill)
        bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self.refill_per_second)
        bucket.last_refill = now

        if bucket.tokens >= cost:
            bucket.tokens -= cost
            return True
        return False

    def remaining(self, key: str) -> float:
        bucket = self._buckets.get(key)
        return float(self.capacity) if bucket is None else bucket.tokens

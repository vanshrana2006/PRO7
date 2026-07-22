"""
Offline tests for TokenBucketLimiter, using an injectable fake clock so
timing behavior is tested deterministically -- no real sleeping, no flaky
timing-dependent assertions.

Run with:  python3 -m unittest tests.test_rate_limiter -v
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.core.rate_limiter import TokenBucketLimiter  # noqa: E402


class FakeClock:
    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestTokenBucketLimiter(unittest.TestCase):
    def test_allows_requests_up_to_capacity(self):
        clock = FakeClock()
        limiter = TokenBucketLimiter(capacity=3, refill_per_second=1, clock=clock)
        self.assertTrue(limiter.allow("user1"))
        self.assertTrue(limiter.allow("user1"))
        self.assertTrue(limiter.allow("user1"))

    def test_rejects_request_beyond_capacity(self):
        clock = FakeClock()
        limiter = TokenBucketLimiter(capacity=2, refill_per_second=1, clock=clock)
        self.assertTrue(limiter.allow("user1"))
        self.assertTrue(limiter.allow("user1"))
        self.assertFalse(limiter.allow("user1"))

    def test_refills_over_time(self):
        clock = FakeClock()
        limiter = TokenBucketLimiter(capacity=2, refill_per_second=1, clock=clock)
        limiter.allow("user1")
        limiter.allow("user1")
        self.assertFalse(limiter.allow("user1"))
        clock.advance(1.0)  # 1 token refilled
        self.assertTrue(limiter.allow("user1"))
        self.assertFalse(limiter.allow("user1"))

    def test_does_not_refill_beyond_capacity(self):
        clock = FakeClock()
        limiter = TokenBucketLimiter(capacity=2, refill_per_second=1, clock=clock)
        clock.advance(100.0)  # would overflow if not capped
        self.assertEqual(limiter.remaining("user1"), 2.0)

    def test_separate_keys_have_independent_buckets(self):
        clock = FakeClock()
        limiter = TokenBucketLimiter(capacity=1, refill_per_second=1, clock=clock)
        self.assertTrue(limiter.allow("user1"))
        self.assertFalse(limiter.allow("user1"))
        self.assertTrue(limiter.allow("user2"))  # independent bucket

    def test_invalid_capacity_raises(self):
        with self.assertRaises(ValueError):
            TokenBucketLimiter(capacity=0, refill_per_second=1)

    def test_invalid_refill_rate_raises(self):
        with self.assertRaises(ValueError):
            TokenBucketLimiter(capacity=1, refill_per_second=0)

    def test_remaining_reports_full_capacity_for_unknown_key(self):
        limiter = TokenBucketLimiter(capacity=5, refill_per_second=1)
        self.assertEqual(limiter.remaining("never-seen"), 5.0)


if __name__ == "__main__":
    unittest.main()

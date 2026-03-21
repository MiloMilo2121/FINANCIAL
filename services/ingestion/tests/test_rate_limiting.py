"""Tests for Redis rate limiting algorithms using fakeredis."""

import time

import fakeredis
import pytest

from financial_ingestion.rate_limiting.token_bucket import TokenBucketConfig, TokenBucketLimiter
from financial_ingestion.rate_limiting.sliding_window import SlidingWindowConfig, SlidingWindowLimiter


@pytest.fixture
def fake_redis():
    return fakeredis.FakeRedis(decode_responses=True)


class TestTokenBucket:
    def test_allows_initial_requests(self, fake_redis):
        limiter = TokenBucketLimiter(
            fake_redis,
            "test_connector",
            TokenBucketConfig(capacity=5, refill_rate=1.0),
        )
        allowed, remaining = limiter.is_allowed()
        assert allowed is True
        assert remaining < 5

    def test_blocks_when_exhausted(self, fake_redis):
        limiter = TokenBucketLimiter(
            fake_redis,
            "exhausted_connector",
            TokenBucketConfig(capacity=2, refill_rate=0.001),  # Very slow refill
        )
        # Exhaust the bucket
        limiter.is_allowed()
        limiter.is_allowed()
        # Next request should be denied
        allowed, _ = limiter.is_allowed()
        assert allowed is False

    def test_allows_burst_within_capacity(self, fake_redis):
        limiter = TokenBucketLimiter(
            fake_redis,
            "burst_connector",
            TokenBucketConfig(capacity=10, refill_rate=1.0),
        )
        results = [limiter.is_allowed()[0] for _ in range(10)]
        assert all(results), "Should allow burst up to capacity"

    def test_different_connectors_independent(self, fake_redis):
        limiter_a = TokenBucketLimiter(
            fake_redis,
            "connector_a",
            TokenBucketConfig(capacity=1, refill_rate=0.001),
        )
        limiter_b = TokenBucketLimiter(
            fake_redis,
            "connector_b",
            TokenBucketConfig(capacity=10, refill_rate=1.0),
        )
        # Exhaust A
        limiter_a.is_allowed()
        allowed_a, _ = limiter_a.is_allowed()
        assert allowed_a is False

        # B should still work
        allowed_b, _ = limiter_b.is_allowed()
        assert allowed_b is True


class TestSlidingWindow:
    def test_allows_within_limit(self, fake_redis):
        limiter = SlidingWindowLimiter(
            fake_redis,
            "test_sliding",
            SlidingWindowConfig(window_seconds=60, max_requests=5),
        )
        for _ in range(5):
            allowed, _ = limiter.is_allowed()
            assert allowed is True

    def test_blocks_when_limit_reached(self, fake_redis):
        limiter = SlidingWindowLimiter(
            fake_redis,
            "strict_sliding",
            SlidingWindowConfig(window_seconds=60, max_requests=3),
        )
        # Use up all 3 slots
        for _ in range(3):
            limiter.is_allowed()
        # Next should be denied
        allowed, remaining = limiter.is_allowed()
        assert allowed is False
        assert remaining <= 0

    def test_reset_clears_window(self, fake_redis):
        limiter = SlidingWindowLimiter(
            fake_redis,
            "reset_sliding",
            SlidingWindowConfig(window_seconds=60, max_requests=2),
        )
        limiter.is_allowed()
        limiter.is_allowed()
        allowed, _ = limiter.is_allowed()
        assert allowed is False

        limiter.reset()
        allowed_after_reset, _ = limiter.is_allowed()
        assert allowed_after_reset is True

    def test_remaining_decrements_correctly(self, fake_redis):
        limiter = SlidingWindowLimiter(
            fake_redis,
            "remaining_test",
            SlidingWindowConfig(window_seconds=60, max_requests=5),
        )
        _, rem1 = limiter.is_allowed()
        _, rem2 = limiter.is_allowed()
        assert rem2 < rem1, "Remaining should decrease with each allowed request"

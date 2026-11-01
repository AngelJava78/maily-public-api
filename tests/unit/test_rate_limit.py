"""Token bucket per IP (FR-019, research R1), with a fake clock."""

from src.rate_limit import TokenBucketLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_the_capacity_passes_and_the_next_one_waits_one_second() -> None:
    clock = FakeClock()
    limiter = TokenBucketLimiter(60, clock=clock)

    assert all(limiter.check("203.0.113.9") is None for _ in range(60))
    assert limiter.check("203.0.113.9") == 1


def test_one_token_comes_back_every_second_at_60_per_minute() -> None:
    clock = FakeClock()
    limiter = TokenBucketLimiter(60, clock=clock)
    for _ in range(60):
        limiter.check("203.0.113.9")

    clock.now += 1

    assert limiter.check("203.0.113.9") is None
    assert limiter.check("203.0.113.9") == 1


def test_retry_after_grows_with_a_slower_refill() -> None:
    clock = FakeClock()
    limiter = TokenBucketLimiter(3, clock=clock)  # one token every 20 seconds
    for _ in range(3):
        limiter.check("ip")

    assert limiter.check("ip") == 20
    clock.now += 15
    assert limiter.check("ip") == 5


def test_zero_disables_the_limit() -> None:
    limiter = TokenBucketLimiter(0, clock=FakeClock())

    assert all(limiter.check("ip") is None for _ in range(1000))
    assert limiter.tracked == 0


def test_each_ip_has_its_own_bucket() -> None:
    limiter = TokenBucketLimiter(2, clock=FakeClock())
    limiter.check("a")
    limiter.check("a")

    assert limiter.check("a") is not None
    assert limiter.check("b") is None


def test_full_buckets_are_purged_when_the_registry_grows() -> None:
    clock = FakeClock()
    limiter = TokenBucketLimiter(60, clock=clock, purge_threshold=2)
    limiter.check("a")
    limiter.check("b")

    clock.now += 120  # a and b are full again
    limiter.check("c")

    assert limiter.tracked == 1

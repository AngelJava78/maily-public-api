"""Limit of requests per client IP (FR-019, research R1 and R2).

It lives in the application because the platform (Railway, phase 1 of mailysoft-infrastructure) has
no configurable limit. A token bucket per IP: `per_minute` tokens at most, refilled at `per_minute / 60`
per second, so there is no double burst at the edge of a window. The count is per process: with several
replicas the effective limit is `replicas × per_minute`.
"""

import ipaddress
import math
import time
from collections.abc import Callable

from fastapi import Request

from src.exceptions import RateLimitExceededError


class TokenBucketLimiter:
    def __init__(
        self,
        per_minute: int,
        clock: Callable[[], float] = time.monotonic,
        purge_threshold: int = 10_000,
    ) -> None:
        self._capacity = float(per_minute)
        self._refill_per_second = per_minute / 60
        self._clock = clock
        self._purge_threshold = purge_threshold
        # key → (tokens left, when they were counted)
        self._buckets: dict[str, tuple[float, float]] = {}

    @property
    def tracked(self) -> int:
        return len(self._buckets)

    def check(self, key: str) -> int | None:
        """`None` if the request may pass; otherwise the whole seconds (≥ 1) until the next token."""
        if self._capacity <= 0:  # 0 = the limit is applied by the infrastructure
            return None
        now = self._clock()
        tokens = self._tokens(key, now)
        if tokens >= 1:
            self._buckets[key] = (tokens - 1, now)
            if len(self._buckets) > self._purge_threshold:
                self._purge(now)
            return None
        self._buckets[key] = (tokens, now)
        return max(1, math.ceil((1 - tokens) / self._refill_per_second))

    def _tokens(self, key: str, now: float) -> float:
        tokens, counted_at = self._buckets.get(key, (self._capacity, now))
        return min(self._capacity, tokens + (now - counted_at) * self._refill_per_second)

    def _purge(self, now: float) -> None:
        # A full bucket is the same as no bucket: forgetting it bounds the memory.
        full = [key for key in self._buckets if self._tokens(key, now) >= self._capacity]
        for key in full:
            del self._buckets[key]


def client_ip(request: Request, trusted_hops: int) -> str:
    """The client IP: the connection's, or the one the outermost trusted proxy wrote.

    With `trusted_hops = N`, the N-th address from the right of `X-Forwarded-For` (all those headers
    joined in order). The addresses on its left may have been written by the client and are ignored.
    """
    peer = request.client.host if request.client else "unknown"
    if trusted_hops == 0:
        return peer
    forwarded = [
        address.strip()
        for header in request.headers.getlist("x-forwarded-for")
        for address in header.split(",")
        if address.strip()
    ]
    if len(forwarded) < trusted_hops:
        return peer
    try:
        return str(ipaddress.ip_address(forwarded[-trusted_hops]))
    except ValueError:
        return peer


async def enforce_rate_limit(request: Request) -> None:
    """Dependency of the `/api/v1` router; the health routes and the documentation are not limited."""
    limiter: TokenBucketLimiter = request.app.state.rate_limiter
    retry_after = limiter.check(client_ip(request, request.app.state.settings.trusted_proxy_hops))
    if retry_after is not None:
        raise RateLimitExceededError(retry_after)

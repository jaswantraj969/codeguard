"""In-memory per-IP rate limiting for public deployment (SRS addendum §7).

A token bucket per client: `per_minute` requests may burst, refilling at
`per_minute / 60` per second. State lives in one process, which matches the
single-instance free-tier deployment.
"""

import math
import time
from collections.abc import Callable

MAX_TRACKED_CLIENTS = 10_000


class RateLimiter:
    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.capacity = float(per_minute)
        self.refill_per_second = per_minute / 60.0
        self.clock = clock
        self.buckets: dict[str, tuple[float, float]] = {}  # ip -> (tokens, last update)

    @property
    def enabled(self) -> bool:
        return self.capacity > 0

    def check(self, client: str) -> float:
        """Take one token for `client`. Returns 0 if allowed, else seconds to wait."""
        if not self.enabled:
            return 0.0
        now = self.clock()
        tokens, last = self.buckets.get(client, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_per_second)
        if tokens >= 1:
            self.buckets[client] = (tokens - 1, now)
            self._prune(now)
            return 0.0
        self.buckets[client] = (tokens, now)
        return (1 - tokens) / self.refill_per_second

    def _prune(self, now: float) -> None:
        """Forget clients whose buckets have refilled, so memory stays bounded."""
        if len(self.buckets) <= MAX_TRACKED_CLIENTS:
            return
        full_after = self.capacity / self.refill_per_second
        self.buckets = {
            ip: state for ip, state in self.buckets.items() if now - state[1] < full_after
        }


def retry_after_header(seconds: float) -> str:
    return str(max(1, math.ceil(seconds)))

import math
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after: int = 0


class InMemoryRateLimiter:
    """Small single-process sliding-window limiter for expensive endpoints."""

    def __init__(
        self,
        *,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._window = window_seconds
        self._clock = clock
        self._requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, client_id: str, bucket: str, limit: int) -> RateLimitDecision:
        now = self._clock()
        cutoff = now - self._window
        key = (client_id, bucket)
        with self._lock:
            if len(self._requests) > 10_000:
                self._prune(cutoff)
            requests = self._requests[key]
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= limit:
                retry_after = max(1, math.ceil(self._window - (now - requests[0])))
                return RateLimitDecision(False, retry_after)
            requests.append(now)
            return RateLimitDecision(True)

    def _prune(self, cutoff: float) -> None:
        for key, requests in list(self._requests.items()):
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if not requests:
                del self._requests[key]

    def clear(self) -> None:
        with self._lock:
            self._requests.clear()

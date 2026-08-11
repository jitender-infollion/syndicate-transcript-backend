import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock

from fastapi import HTTPException

_lock = Lock()
# Ordered so eviction can pop the true LRU key in O(1), not by scanning.
_hits: "OrderedDict[str, list[float]]" = OrderedDict()

# Keys are never otherwise removed, so this caps growth via an approximate
# budget - measuring real memory per request would be too expensive here.
_MAX_MEMORY_BYTES = 200 * 1024 * 1024  # 200MB
# Measured worst case (OTP_IP_HOURLY, 75 attempts, long IPv6 key) is ~2.6KB;
# rounded up for margin.
_WORST_CASE_BYTES_PER_KEY = 3_000
_MAX_KEYS = _MAX_MEMORY_BYTES // _WORST_CASE_BYTES_PER_KEY


def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    # In-memory sliding window, single-process only - needs Redis/Postgres for multi-worker.
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        timestamps = _hits.get(key)
        if timestamps is None:
            timestamps = []
            _hits[key] = timestamps  # new keys land at the MRU end already
        else:
            _hits.move_to_end(key)

        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)
        if len(timestamps) >= max_requests:
            raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.")
        timestamps.append(now)

        # Evict LRU keys once over budget - active keys stay protected (touched
        # = moved to MRU), except under a deliberate flood of unique keys, an
        # accepted tradeoff of any capacity-bounded cache.
        while len(_hits) > _MAX_KEYS:
            _hits.popitem(last=False)


def reset_rate_limits() -> None:
    """Test-only: clears all counters so one test's requests don't bleed into another's."""
    with _lock:
        _hits.clear()


@dataclass(frozen=True)
class RateLimitPolicy:
    max_attempts: int
    window_seconds: int

    def check(self, key: str) -> None:
        check_rate_limit(key, self.max_attempts, self.window_seconds)


class RateLimits:
    # OTP retries/login lockout/reset cooldown are DB-tracked instead, next to their handlers.
    class auth:
        REGISTER_IP = RateLimitPolicy(max_attempts=10, window_seconds=3600)
        # Higher ceiling - offices/NAT share one IP across many logins.
        LOGIN_IP = RateLimitPolicy(max_attempts=20, window_seconds=600)
        LOGIN_OTP_IP = RateLimitPolicy(max_attempts=10, window_seconds=3600)
        FORGOT_PASSWORD_IP = RateLimitPolicy(max_attempts=10, window_seconds=3600)

        # OTP generation caps, separate from IP limits and the wrong-guess lockout.
        OTP_EMAIL_BURST = RateLimitPolicy(max_attempts=5, window_seconds=600)
        OTP_EMAIL_HOURLY = RateLimitPolicy(max_attempts=8, window_seconds=3600)
        OTP_EMAIL_DAILY = RateLimitPolicy(max_attempts=15, window_seconds=86400)
        OTP_IP_BURST = RateLimitPolicy(max_attempts=15, window_seconds=600)
        OTP_IP_HOURLY = RateLimitPolicy(max_attempts=75, window_seconds=3600)
        OTP_RESEND_COOLDOWN = RateLimitPolicy(max_attempts=1, window_seconds=45)

    class orders:
        # Keyed by user_id - create_order requires auth and each call hits Razorpay.
        CREATE_ORDER = RateLimitPolicy(max_attempts=20, window_seconds=600)

    class inquiries:
        # Public, unauthenticated endpoints - rate limited by IP instead.
        SUPPORT_MESSAGE = RateLimitPolicy(max_attempts=5, window_seconds=600)
        TOPIC_REQUEST = RateLimitPolicy(max_attempts=5, window_seconds=600)

    class transcripts:
        # Public browse endpoints (list/filter/domains/detail) share one IP bucket.
        PUBLIC_IP = RateLimitPolicy(max_attempts=20, window_seconds=60)

    class general:
        # Broad catch-alls applied in jwt_middleware, on top of any specific policy above.
        PUBLIC_IP = RateLimitPolicy(max_attempts=20, window_seconds=60)
        AUTHENTICATED_USER = RateLimitPolicy(max_attempts=20, window_seconds=60)

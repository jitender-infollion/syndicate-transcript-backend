import time
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock

from fastapi import HTTPException

_lock = Lock()
_hits: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    # In-memory sliding window, single-process only - move to Postgres/Redis
    # if this ever runs as more than one worker/replica.
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        timestamps = _hits[key]
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)
        if len(timestamps) >= max_requests:
            raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.")
        timestamps.append(now)


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
    # Account-based counters (OTP retries, login lockout, reset cooldown) are
    # DB-tracked instead and live next to the handlers that use them.
    class auth:
        REGISTER_IP = RateLimitPolicy(max_attempts=10, window_seconds=3600)
        # Higher ceiling - offices/NAT share one IP across many logins.
        LOGIN_IP = RateLimitPolicy(max_attempts=20, window_seconds=600)
        LOGIN_OTP_IP = RateLimitPolicy(max_attempts=10, window_seconds=3600)
        FORGOT_PASSWORD_IP = RateLimitPolicy(max_attempts=10, window_seconds=3600)

        # OTP generation caps, separate from IP limits and the wrong-guess lockout.
        OTP_EMAIL_BURST = RateLimitPolicy(max_attempts=3, window_seconds=600)
        OTP_EMAIL_HOURLY = RateLimitPolicy(max_attempts=8, window_seconds=3600)
        OTP_EMAIL_DAILY = RateLimitPolicy(max_attempts=15, window_seconds=86400)
        OTP_IP_BURST = RateLimitPolicy(max_attempts=15, window_seconds=600)
        OTP_IP_HOURLY = RateLimitPolicy(max_attempts=75, window_seconds=3600)
        OTP_RESEND_COOLDOWN = RateLimitPolicy(max_attempts=1, window_seconds=45)

    class orders:
        # Keyed by user_id, not IP - create_order already requires auth, and
        # each attempt is a real Razorpay API call.
        CREATE_ORDER = RateLimitPolicy(max_attempts=20, window_seconds=600)

    class inquiries:
        # Public, unauthenticated endpoints - rate limited by IP instead.
        SUPPORT_MESSAGE = RateLimitPolicy(max_attempts=5, window_seconds=600)
        TOPIC_REQUEST = RateLimitPolicy(max_attempts=5, window_seconds=600)

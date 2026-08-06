import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException

_lock = Lock()
_hits: dict[str, list[float]] = defaultdict(list)


def check_ip_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    """In-memory sliding-window limiter, keyed by an arbitrary string (e.g.
    "register:203.0.113.4"). Single-process only - each worker/instance keeps
    its own counts, so this doesn't hold up if this service ever runs as more
    than one replica/worker. Good enough for now; move to a shared store
    (Postgres or Redis) if that changes.
    """
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        timestamps = _hits[key]
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)
        if len(timestamps) >= max_requests:
            raise HTTPException(
                status_code=429, detail="Too many attempts from this network. Please try again later."
            )
        timestamps.append(now)


def reset_rate_limits() -> None:
    """Test-only: clears all counters so one test's requests don't bleed into another's."""
    with _lock:
        _hits.clear()

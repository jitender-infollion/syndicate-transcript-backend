from fastapi import HTTPException, Request

from config import get_settings


def verify_same_origin(request: Request) -> None:
    # CSRF guard for cookie-authenticated endpoints - CORS alone doesn't stop the
    # request itself, only reading the response. Missing Origin/Referer is rejected.
    allowed_origins = get_settings().services.cors_origins
    origin = request.headers.get("origin")
    if not origin:
        referer = request.headers.get("referer", "")
        # Referer carries a full path; Origin is scheme+host+port only.
        parts = referer.split("/")
        origin = "/".join(parts[:3]) if len(parts) >= 3 else None
    if not origin or origin not in allowed_origins:
        raise HTTPException(status_code=403, detail="Cross-origin request blocked.")

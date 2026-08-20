import re

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from apis.rate_limiting.limiter import RateLimitPolicy, RateLimits
from apis.security import decode_access_token
from config import get_settings
from utils.request_meta import get_ip_address
from utils.response import error_response

# Per-request auth gate: public, soft-auth, or requires login. Also applies
# the two generic rate-limit catch-alls (IP for public/soft-auth, user for
# authenticated) that apply to every request regardless of route. Anything
# more specific (per-endpoint IP limits, OTP-generation limits, etc.) lives as
# route-level dependencies in apis/rate_limiting/dependencies.py instead, so
# this file stays a simple, business-logic-free auth gate.

# Dynamic id - scoped to one segment so /me/purchased, /{id}/view|download stay protected.
PUBLIC_PATH_RE = re.compile(r"^/api/transcripts/[^/]+$")

# Also public, like the detail page itself - unlike /view|download|full-text,
# there's no entitlement being checked here, just a read-only recommendation list.
PUBLIC_TRANSCRIPT_SUBPATH_RE = re.compile(r"^/api/transcripts/[^/]+/similar$")

WEBHOOK_PATH_RE = re.compile(r"^/api/orders/webhook/[^/]+$")  # verified via gateway signature instead

# Server-to-server transcript ingest from the Infollion backend - authenticated by a
# shared x-api-key at the route level (see apis/dependencies.verify_ingest_api_key),
# so it bypasses the JWT gate. Treated like webhooks: exempt from IP rate-limiting too.
INGEST_PATH_RE = re.compile(r"^/api/internal/transcripts(/[^/]+)?$")

# Bearer token decoded if present, but not required. /api/cart/merge excluded.
SOFT_AUTH_PATHS = {"/api/cart", "/api/support", "/api/topics/request"}
SOFT_AUTH_PATH_RE = re.compile(r"^/api/cart/items(/[^/]+)?$")

_DOCS_PATHS = {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"} if get_settings().services.enable_docs else set()

UNPROTECTED_PATHS = {
    "/health",
    *_DOCS_PATHS,
    "/api/auth/register",
    "/api/auth/register/verify-otp",
    "/api/auth/register/resend-otp",
    "/api/auth/login",
    "/api/auth/login/otp/send",
    "/api/auth/login/otp/verify",
    "/api/auth/refresh",
    "/api/auth/logout",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
    "/api/transcripts",
    "/api/transcripts/domains",
}


def _rate_limit_response(policy: RateLimitPolicy, key: str) -> JSONResponse | None:
    try:
        policy.check(key)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content=error_response(str(exc.detail)))
    return None


async def jwt_middleware(request: Request, call_next):
    path = request.url.path

    # Fully public, unauthenticated - webhooks excluded (server-to-server,
    # protected by gateway signature instead; IP-limiting them risks dropping
    # legitimate redelivery bursts from the gateway's own IP pool).
    if (
        path in UNPROTECTED_PATHS
        or PUBLIC_PATH_RE.match(path)
        or PUBLIC_TRANSCRIPT_SUBPATH_RE.match(path)
        or WEBHOOK_PATH_RE.match(path)
        or INGEST_PATH_RE.match(path)
    ):
        if not (WEBHOOK_PATH_RE.match(path) or INGEST_PATH_RE.match(path)):
            ip_address = get_ip_address(request)
            if ip_address:
                blocked = _rate_limit_response(RateLimits.general.PUBLIC_IP, f"public:{ip_address}")
                if blocked:
                    return blocked
        return await call_next(request)

    # Soft-auth: optional login, but still unauthenticated-reachable.
    if path in SOFT_AUTH_PATHS or SOFT_AUTH_PATH_RE.match(path):
        ip_address = get_ip_address(request)
        if ip_address:
            blocked = _rate_limit_response(RateLimits.general.PUBLIC_IP, f"public:{ip_address}")
            if blocked:
                return blocked

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            payload = decode_access_token(auth_header.removeprefix("Bearer ").strip())
            if payload:
                request.state.user_id = payload.get("user_id")
        return await call_next(request)

    # Hard auth required.
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content=error_response("Not authenticated"))

    token = auth_header.removeprefix("Bearer ").strip()
    payload = decode_access_token(token)
    if payload is None:
        return JSONResponse(status_code=401, content=error_response("Invalid or expired token"))

    request.state.user_id = payload.get("user_id")
    request.state.user_name = payload.get("user_name")
    request.state.email = payload.get("email")

    blocked = _rate_limit_response(RateLimits.general.AUTHENTICATED_USER, f"user:{request.state.user_id}")
    if blocked:
        return blocked

    return await call_next(request)

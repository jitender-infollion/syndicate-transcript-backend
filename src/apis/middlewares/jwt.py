import re

from fastapi import Request
from fastapi.responses import JSONResponse

from apis.security import decode_access_token
from config import get_settings
from utils.response import error_response

# Per-request auth gate: public, soft-auth, or requires login.

# Dynamic id - scoped to one segment so /me/purchased, /{id}/view|download stay protected.
PUBLIC_PATH_RE = re.compile(r"^/api/transcripts/[^/]+$")

WEBHOOK_PATH_RE = re.compile(r"^/api/orders/webhook/[^/]+$")  # verified via gateway signature instead

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


async def jwt_middleware(request: Request, call_next):
    path = request.url.path
    if path in UNPROTECTED_PATHS or PUBLIC_PATH_RE.match(path) or WEBHOOK_PATH_RE.match(path):
        return await call_next(request)

    if path in SOFT_AUTH_PATHS or SOFT_AUTH_PATH_RE.match(path):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            payload = decode_access_token(auth_header.removeprefix("Bearer ").strip())
            if payload:
                request.state.user_id = payload.get("user_id")
        return await call_next(request)

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
    return await call_next(request)

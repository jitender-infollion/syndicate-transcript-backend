import re

from fastapi import Request
from fastapi.responses import JSONResponse

from apis.security import decode_access_token
from utils.response import error_response

# Transcript detail has a dynamic id segment, so it can't sit in the exact-
# match UNPROTECTED_PATHS set like /api/transcripts and /api/transcripts/
# domains do. Fully public (no identity needed at all - the detail response
# no longer varies by caller), matched with a regex instead. Matches only a
# single extra path segment, so /api/transcripts/me/purchased and
# /api/transcripts/{id}/view|download - which must stay hard-protected -
# don't accidentally qualify.
PUBLIC_PATH_RE = re.compile(r"^/api/transcripts/[^/]+$")

# Payment gateway webhooks are server-to-server calls from the gateway (e.g.
# Razorpay) - they never carry a Bearer token. Authenticity is verified inside
# the route itself via the gateway's own signature header, not a JWT.
WEBHOOK_PATH_RE = re.compile(r"^/api/orders/webhook/[^/]+$")

# Cart add/view/remove must work for both anonymous and logged-in callers, so
# these paths never 401 - but if a valid Bearer token IS present, it's still
# decoded and attached, so routes can tell a guest from a logged-in user.
# /api/cart/merge is deliberately NOT included here: merging into "your
# account" requires a real logged-in identity, so it falls through to the
# hard-auth branch below like every other protected route.
#
# Support/topic-request submissions are public (anyone can submit, no account
# needed) but still opportunistically record who it was if the submitter
# happened to be logged in - unlike UNPROTECTED_PATHS, soft-auth still decodes
# a Bearer token when one is present, it just never requires one.
SOFT_AUTH_PATHS = {"/api/cart", "/api/support", "/api/topics/request"}
SOFT_AUTH_PATH_RE = re.compile(r"^/api/cart/items(/[^/]+)?$")

UNPROTECTED_PATHS = {
    "/health",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/openapi.json",
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

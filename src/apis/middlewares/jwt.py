from fastapi import Request
from fastapi.responses import JSONResponse

from apis.security import decode_access_token
from utils.response import error_response

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
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
}


async def jwt_middleware(request: Request, call_next):
    if request.url.path in UNPROTECTED_PATHS:
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

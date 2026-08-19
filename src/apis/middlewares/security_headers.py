from fastapi import Request

# Cheap, standard hardening headers with no behavior risk - applied to every
# response regardless of route. HSTS is harmless to send over plain HTTP in
# local dev too: browsers only honor it on responses actually received over
# HTTPS, so it's a no-op there and only takes effect in real deployments.


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response

from fastapi import Request

from config import get_settings


def get_ip_address(request: Request) -> str | None:
    if get_settings().services.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Leftmost entry is the original client, appended by the first
            # proxy hop closest to them - trustworthy only because
            # TRUST_PROXY_HEADERS means every request here already passes
            # through our own reverse proxy first, which overwrites this
            # header rather than forwarding whatever the client sent.
            first_hop = forwarded.split(",")[0].strip()
            if first_hop:
                return first_hop
    return request.client.host if request.client else None


def get_device_info(request: Request) -> str | None:
    return request.headers.get("user-agent")

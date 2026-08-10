from fastapi import Request


def get_ip_address(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_device_info(request: Request) -> str | None:
    return request.headers.get("user-agent")

from fastapi import Response

REFRESH_COOKIE_NAME = "refresh_token"
GUEST_CART_COOKIE_NAME = "guest_cart_id"


def set_refresh_cookie(response: Response, token: str, secure: bool, max_age_days: int) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=max_age_days * 86400,
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
        path="/api/auth",
    )


def clear_refresh_cookie(response: Response, secure: bool) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/auth",
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
    )


def set_guest_cart_cookie(response: Response, guest_id: str, secure: bool, max_age_days: int = 180) -> None:
    response.set_cookie(
        key=GUEST_CART_COOKIE_NAME,
        value=guest_id,
        max_age=max_age_days * 86400,
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
        path="/api/cart",
    )


def clear_guest_cart_cookie(response: Response, secure: bool) -> None:
    response.delete_cookie(
        key=GUEST_CART_COOKIE_NAME,
        path="/api/cart",
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
    )

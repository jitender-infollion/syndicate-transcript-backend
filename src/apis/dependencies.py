from fastapi import HTTPException, Request


def get_current_user_id(request: Request) -> int:
    """User id attached by the JWT middleware. Use on every protected route."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="User identity missing from session.")
    return int(user_id)


def get_current_user_id_optional(request: Request) -> int | None:
    """Like get_current_user_id, but None instead of a 401 when there's no valid token.

    For soft-auth routes (e.g. cart) that must work for both guests and
    logged-in users - the JWT middleware only ever sets request.state.user_id
    when a valid Bearer token was actually presented on those paths.
    """
    user_id = getattr(request.state, "user_id", None)
    return int(user_id) if user_id else None

from fastapi import HTTPException, Request


def get_current_user_id(request: Request) -> int:
    """User id attached by the JWT middleware. Use on every protected route."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="User identity missing from session.")
    return int(user_id)

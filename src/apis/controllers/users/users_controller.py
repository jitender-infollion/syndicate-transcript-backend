from .users_handler import handle_get_profile
from .users_schema import ProfileResponse


def get_profile(user_id: int) -> ProfileResponse:
    return handle_get_profile(user_id)

import uuid

from .users_handler import handle_get_profile
from .users_schema import ProfileResponse


def get_profile(user_id: uuid.UUID) -> ProfileResponse:
    return handle_get_profile(user_id)

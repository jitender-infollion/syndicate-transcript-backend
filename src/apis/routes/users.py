import uuid

from fastapi import APIRouter, Depends

from apis.controllers.users import users_controller
from apis.dependencies import get_current_user_id
from utils.response import success_response

from .paths import P

router = APIRouter(prefix=P.users.BASE, tags=["Users"])


@router.get(P.users.ME)
def get_me(user_id: uuid.UUID = Depends(get_current_user_id)):
    result = users_controller.get_profile(user_id)
    return success_response(data=result)

from fastapi import APIRouter

from utils.response import success_response

from .paths import P

router = APIRouter()


@router.get(P.system.HEALTH)
async def health():
    return success_response(data={"service": "syndicate-transcript-backend"}, message="ok")

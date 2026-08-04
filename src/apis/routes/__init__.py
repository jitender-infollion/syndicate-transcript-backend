from fastapi import APIRouter

from .auth import router as auth_router
from .cart import router as cart_router
from .transcripts import router as transcripts_router
from .users import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(transcripts_router)
api_router.include_router(cart_router)

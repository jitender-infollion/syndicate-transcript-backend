import logging

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from apis.middlewares.jwt import jwt_middleware
from apis.routes import api_router
from config import get_settings
from logging_config import setup_logging
from utils.response import error_response

setup_logging()
logger = logging.getLogger(__name__)

_docs_enabled = get_settings().services.enable_docs
app = FastAPI(
    title="Syndicate Transcript Backend",
    version="1.0.0",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

app.add_middleware(BaseHTTPMiddleware, dispatch=jwt_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().services.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Outermost: assign/propagate X-Request-ID so every log line carries the correlation id.
app.add_middleware(CorrelationIdMiddleware)

app.include_router(api_router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    # detail can be a dict ({"message": ..., "data": ...}) for structured errors.
    if isinstance(exc.detail, dict):
        message = exc.detail.get("message", "Error")
        data = exc.detail.get("data")
        return JSONResponse(status_code=exc.status_code, content=error_response(message, data))
    return JSONResponse(status_code=exc.status_code, content=error_response(str(exc.detail)))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = exc.errors()
    message = errors[0]["msg"] if errors else "Validation error"
    return JSONResponse(status_code=422, content=error_response(message))

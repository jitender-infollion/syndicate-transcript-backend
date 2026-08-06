from fastapi import APIRouter, HTTPException, Request, Response

from apis.controllers.auth import auth_controller
from apis.controllers.auth.auth_schema import (
    ForgotPasswordRequest,
    LoginOtpSendRequest,
    LoginOtpVerifyRequest,
    LoginRequest,
    RegisterRequest,
    ResendOtpRequest,
    ResetPasswordRequest,
    VerifyOtpRequest,
)
from config import get_settings
from utils.cookies import REFRESH_COOKIE_NAME, clear_refresh_cookie, set_refresh_cookie
from utils.response import success_response

from .paths import P

router = APIRouter(prefix=P.auth.BASE, tags=["Auth"])


def _device_info(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _ip_address(request: Request) -> str | None:
    return request.client.host if request.client else None


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    auth_settings = get_settings().auth
    set_refresh_cookie(response, raw_token, auth_settings.cookie_secure, auth_settings.refresh_token_expiry_days)


@router.post(P.auth.REGISTER)
def register(data: RegisterRequest, request: Request):
    result = auth_controller.register(data, _ip_address(request))
    return success_response(data=result, message="OTP sent to your email. Please verify to complete registration.")


@router.post(P.auth.REGISTER_VERIFY_OTP)
def verify_registration_otp(data: VerifyOtpRequest, request: Request, response: Response):
    auth_response, raw_refresh_token = auth_controller.verify_registration_otp(
        data, _device_info(request), _ip_address(request)
    )
    _set_refresh_cookie(response, raw_refresh_token)
    return success_response(data=auth_response, message="Registration successful.")


@router.post(P.auth.REGISTER_RESEND_OTP)
def resend_otp(data: ResendOtpRequest):
    result = auth_controller.resend_otp(data)
    return success_response(data=result, message="A new OTP has been sent to your email.")


@router.post(P.auth.LOGIN)
def login(data: LoginRequest, request: Request, response: Response):
    auth_response, raw_refresh_token = auth_controller.login(data, _device_info(request), _ip_address(request))
    _set_refresh_cookie(response, raw_refresh_token)
    return success_response(data=auth_response, message="Login successful.")


@router.post(P.auth.LOGIN_OTP_SEND)
def send_login_otp(data: LoginOtpSendRequest):
    result = auth_controller.send_login_otp(data)
    return success_response(data=result, message="OTP sent to your email.")


@router.post(P.auth.LOGIN_OTP_VERIFY)
def verify_login_otp(data: LoginOtpVerifyRequest, request: Request, response: Response):
    auth_response, raw_refresh_token = auth_controller.verify_login_otp(
        data, _device_info(request), _ip_address(request)
    )
    _set_refresh_cookie(response, raw_refresh_token)
    return success_response(data=auth_response, message="Login successful.")


@router.post(P.auth.REFRESH)
def refresh(request: Request, response: Response):
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")
    auth_response, new_raw_refresh_token = auth_controller.refresh(
        raw_token, _device_info(request), _ip_address(request)
    )
    _set_refresh_cookie(response, new_raw_refresh_token)
    return success_response(data=auth_response, message="Token refreshed.")


@router.post(P.auth.FORGOT_PASSWORD)
def forgot_password(data: ForgotPasswordRequest):
    auth_controller.forgot_password(data)
    return success_response(message="Password reset link has been sent to your email.")


@router.post(P.auth.RESET_PASSWORD)
def reset_password(data: ResetPasswordRequest):
    auth_controller.reset_password(data)
    return success_response(message="Password reset successful.")


@router.post(P.auth.LOGOUT)
def logout(request: Request, response: Response):
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    auth_controller.logout(raw_token)
    clear_refresh_cookie(response, get_settings().auth.cookie_secure)
    return success_response(message="Logged out successfully.")

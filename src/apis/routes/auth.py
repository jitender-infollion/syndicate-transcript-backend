from fastapi import APIRouter, Depends

from apis.controllers.auth import auth_controller
from apis.controllers.auth.auth_schema import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResendOtpRequest,
    ResetPasswordRequest,
    VerifyOtpRequest,
)
from apis.dependencies import get_current_user_id
from utils.response import success_response

from .paths import P

router = APIRouter(prefix=P.auth.BASE, tags=["Auth"])


@router.post(P.auth.REGISTER)
def register(data: RegisterRequest):
    result = auth_controller.register(data)
    return success_response(data=result, message="OTP sent to your email. Please verify to complete registration.")


@router.post(P.auth.REGISTER_VERIFY_OTP)
def verify_registration_otp(data: VerifyOtpRequest):
    result = auth_controller.verify_registration_otp(data)
    return success_response(data=result, message="Registration successful.")


@router.post(P.auth.REGISTER_RESEND_OTP)
def resend_otp(data: ResendOtpRequest):
    result = auth_controller.resend_otp(data)
    return success_response(data=result, message="A new OTP has been sent to your email.")


@router.post(P.auth.LOGIN)
def login(data: LoginRequest):
    result = auth_controller.login(data)
    return success_response(data=result, message="Login successful.")


@router.post(P.auth.FORGOT_PASSWORD)
def forgot_password(data: ForgotPasswordRequest):
    auth_controller.forgot_password(data)
    return success_response(message="If that email exists, a reset link has been sent.")


@router.post(P.auth.RESET_PASSWORD)
def reset_password(data: ResetPasswordRequest):
    auth_controller.reset_password(data)
    return success_response(message="Password reset successful.")


@router.post(P.auth.LOGOUT)
def logout(user_id: int = Depends(get_current_user_id)):
    auth_controller.logout(user_id)
    return success_response(message="Logged out successfully.")

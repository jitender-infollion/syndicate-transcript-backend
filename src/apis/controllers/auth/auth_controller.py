from .auth_handler import (
    handle_forgot_password,
    handle_login,
    handle_logout,
    handle_register,
    handle_resend_otp,
    handle_reset_password,
    handle_verify_registration_otp,
)
from .auth_schema import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    PendingAuthResponse,
    RegisterRequest,
    ResendOtpRequest,
    ResetPasswordRequest,
    VerifyOtpRequest,
)
from .auth_validator import validate_otp_format, validate_password


def register(data: RegisterRequest) -> PendingAuthResponse:
    validate_password(data.password)
    return handle_register(data)


def verify_registration_otp(data: VerifyOtpRequest) -> AuthResponse:
    validate_otp_format(data.otp)
    return handle_verify_registration_otp(data.pendingToken, data.otp)


def resend_otp(data: ResendOtpRequest) -> PendingAuthResponse:
    return handle_resend_otp(data.pendingToken)


def login(data: LoginRequest) -> AuthResponse:
    return handle_login(data.email, data.password)


def forgot_password(data: ForgotPasswordRequest) -> None:
    handle_forgot_password(data.email)


def reset_password(data: ResetPasswordRequest) -> None:
    validate_password(data.password)
    handle_reset_password(data.token, data.password)


def logout(user_id: int) -> None:
    handle_logout(user_id)

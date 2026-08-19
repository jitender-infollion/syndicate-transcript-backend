import uuid

from fastapi import Depends, Request

from apis.controllers.auth.auth_schema import LoginOtpSendRequest, RegisterRequest, ResendOtpRequest
from apis.dependencies import get_current_user_id
from apis.models.user import User
from apis.rate_limiting.limiter import RateLimits
from apis.security import decode_pending_verification_token
from services.crypto.email_crypto import hash_email
from services.database.postgres.connection import get_session
from utils.request_meta import get_ip_address

# Endpoint-specific rate limits, wired onto routes via dependencies=[Depends(...)].
# The generic IP/user catch-alls that apply to every request regardless of
# route live in apis/middlewares/jwt.py instead - this file is only for
# limits that need to know something about the specific endpoint (its parsed
# body, or account state), keeping jwt_middleware a simple, business-logic-free
# auth gate.


def _enforce_otp_generation_limits(purpose: str, email: str, ip_address: str | None) -> None:
    # Caps OTP generation itself, not just wrong guesses. Keyed per purpose so
    # a signup's counters can't block an unrelated login-OTP request.
    email_key = hash_email(email)
    RateLimits.auth.OTP_RESEND_COOLDOWN.check(f"otp_cooldown:{purpose}:{email_key}")
    RateLimits.auth.OTP_EMAIL_BURST.check(f"otp_email_burst:{purpose}:{email_key}")
    RateLimits.auth.OTP_EMAIL_HOURLY.check(f"otp_email_hourly:{purpose}:{email_key}")
    RateLimits.auth.OTP_EMAIL_DAILY.check(f"otp_email_daily:{purpose}:{email_key}")
    if ip_address:
        RateLimits.auth.OTP_IP_BURST.check(f"otp_ip_burst:{purpose}:{ip_address}")
        RateLimits.auth.OTP_IP_HOURLY.check(f"otp_ip_hourly:{purpose}:{ip_address}")


def rate_limit_register(request: Request, data: RegisterRequest) -> None:
    ip_address = get_ip_address(request)
    if ip_address:
        RateLimits.auth.REGISTER_IP.check(f"register:{ip_address}")

    session = get_session()
    try:
        existing = session.query(User).filter(User.email_hash == hash_email(data.email)).first()
        # Already registered and verified - the handler 409s without sending
        # an OTP, so don't burn OTP quota over a request that sends nothing.
        if not (existing and existing.email_verified):
            _enforce_otp_generation_limits("register", data.email, ip_address)
    finally:
        session.close()


def rate_limit_resend_otp(request: Request, data: ResendOtpRequest) -> None:
    ip_address = get_ip_address(request)
    user_id = decode_pending_verification_token(data.tempToken)
    if user_id is None:
        return
    session = get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        # Already verified - the handler will 409 without sending an OTP, so
        # don't burn OTP quota over a request that was never going to send one.
        if user and not user.email_verified:
            _enforce_otp_generation_limits("register", user.email, ip_address)
    finally:
        session.close()


def rate_limit_login(request: Request) -> None:
    ip_address = get_ip_address(request)
    if ip_address:
        RateLimits.auth.LOGIN_IP.check(f"login:{ip_address}")


def rate_limit_login_otp_send(request: Request, data: LoginOtpSendRequest) -> None:
    ip_address = get_ip_address(request)
    if ip_address:
        RateLimits.auth.LOGIN_OTP_IP.check(f"login_otp:{ip_address}")

    session = get_session()
    try:
        user = session.query(User).filter(User.email_hash == hash_email(data.email)).first()
        # Handler 401s immediately for a missing/inactive/unverified account
        # without sending an OTP - don't burn OTP quota over a request that
        # sends nothing (e.g. probing random/nonexistent emails).
        if user and user.active and user.email_verified:
            _enforce_otp_generation_limits("login", data.email, ip_address)
    finally:
        session.close()


def rate_limit_forgot_password(request: Request) -> None:
    ip_address = get_ip_address(request)
    if ip_address:
        RateLimits.auth.FORGOT_PASSWORD_IP.check(f"forgot_password:{ip_address}")


def rate_limit_support(request: Request) -> None:
    ip_address = get_ip_address(request)
    if ip_address:
        RateLimits.inquiries.SUPPORT_MESSAGE.check(f"support:{ip_address}")


def rate_limit_topic_request(request: Request) -> None:
    ip_address = get_ip_address(request)
    if ip_address:
        RateLimits.inquiries.TOPIC_REQUEST.check(f"topic_request:{ip_address}")


def rate_limit_transcripts_public(request: Request) -> None:
    ip_address = get_ip_address(request)
    if ip_address:
        RateLimits.transcripts.PUBLIC_IP.check(f"transcripts_public:{ip_address}")


def rate_limit_create_order(user_id: uuid.UUID = Depends(get_current_user_id)) -> None:
    RateLimits.orders.CREATE_ORDER.check(f"create_order:{user_id}")

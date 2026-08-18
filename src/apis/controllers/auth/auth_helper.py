import hashlib
import math
import secrets
import hmac
from datetime import datetime, timedelta

from fastapi import HTTPException

from apis.models.session import Session
from apis.models.user import User
from apis.security import create_access_token, decode_pending_verification_token
from config import get_settings
from services.crypto.otp_crypto import hash_otp

from .auth_schema import AuthResponse, AuthUserResponse

INVALID_SESSION_DETAIL = "Your verification session has expired. Please sign in again to resume verification."


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_otp(session, user: User, expiry_minutes: int, max_attempts: int, cooldown_minutes: int) -> str:
    # Cooldown only kicks in once the current outstanding code's attempts are
    # exhausted - a user who hasn't guessed wrong yet can resend anytime.
    if user.otp_retry_count >= max_attempts and user.otp_expire_time is not None:
        issued_at = user.otp_expire_time - timedelta(minutes=expiry_minutes)
        cooldown_ends_at = issued_at + timedelta(minutes=cooldown_minutes)
        remaining = cooldown_ends_at - datetime.utcnow()
        if remaining.total_seconds() > 0:
            wait_minutes = max(1, math.ceil(remaining.total_seconds() / 60))
            raise HTTPException(
                status_code=429,
                detail=f"Too many attempts. Please try again in {wait_minutes} minute"
                f"{'s' if wait_minutes != 1 else ''}.",
            )

    otp_code = generate_otp()
    user.otp_hash = hash_otp(otp_code)
    user.otp_expire_time = datetime.utcnow() + timedelta(minutes=expiry_minutes)
    user.otp_retry_count = 0
    return otp_code


def verify_otp(session, user: User, otp: str, max_attempts: int) -> None:
    if not user.otp_hash or user.otp_expire_time is None:
        raise HTTPException(status_code=400, detail="No OTP found. Please request a new one.")
    if user.otp_expire_time < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
    if user.otp_retry_count >= max_attempts:
        raise HTTPException(status_code=429, detail="Too many incorrect attempts. Please request a new OTP.")
    if not hmac.compare_digest(hash_otp(otp), user.otp_hash):
        user.otp_retry_count += 1
        session.commit()
        raise HTTPException(status_code=400, detail="Invalid OTP.")

    # Single-use: nothing left to match against on replay.
    user.otp_hash = None
    user.otp_expire_time = None
    user.otp_retry_count = 0


def build_auth_response(user: User) -> AuthResponse:
    token = create_access_token(user_id=user.id, user_name=user.name, email=user.email)
    return AuthResponse(
        token=token,
        user=AuthUserResponse(id=str(user.id), name=user.name, email=user.email, companyName=user.company_name),
    )


def create_refresh_session(session, user: User, device_info: str | None, ip_address: str | None) -> str:
    raw_token = secrets.token_urlsafe(32)
    session.add(
        Session(
            user_id=user.id,
            refresh_token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            device_info=device_info,
            ip_address=ip_address,
            expires_at=datetime.utcnow() + timedelta(days=get_settings().auth.refresh_token_expiry_days),
        )
    )
    return raw_token


def authenticate_user(session, user: User, device_info: str | None, ip_address: str | None) -> tuple[AuthResponse, str]:
    auth_response = build_auth_response(user)
    refresh_token = create_refresh_session(session, user, device_info, ip_address)
    return auth_response, refresh_token


def get_pending_verification_user(session, temp_token: str) -> User:
    user_id = decode_pending_verification_token(temp_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail=INVALID_SESSION_DETAIL)
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail=INVALID_SESSION_DETAIL)
    return user

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from config import get_settings

JWT_ALGORITHM = "HS256"
PENDING_VERIFICATION_PURPOSE = "email_verification"
PENDING_VERIFICATION_EXPIRY_MINUTES = 15
OTP_LOGIN_PURPOSE = "otp_login"
OTP_LOGIN_EXPIRY_MINUTES = 10


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(*, user_id: int, user_name: str, email: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": str(user_id),
        "user_name": user_name,
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.auth.access_token_expiry_minutes),
    }
    return jwt.encode(payload, settings.auth.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode a Bearer token, trying this service's own secret first, then any
    additionally trusted secrets (e.g. tokens issued by the main Infollion
    platform during the SSO handoff). Returns None if the token is invalid or
    expired under every configured secret."""
    settings = get_settings()
    secrets_to_try = [settings.auth.jwt_secret, *settings.auth.trusted_jwt_secrets]
    for secret in secrets_to_try:
        try:
            return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        except JWTError:
            continue
    return None


def create_pending_verification_token(user_id: int) -> str:
    """A short-lived token that stands in for a real access token while an
    account is unverified. Carries only user_id (no name/email claims) so it
    can't be mistaken for a real access token by decode_access_token, since
    JWT_ALGORITHM/secret are shared but the claim shape differs."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "purpose": PENDING_VERIFICATION_PURPOSE,
        "user_id": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=PENDING_VERIFICATION_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, settings.auth.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_pending_verification_token(token: str) -> int | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.auth.jwt_secret, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("purpose") != PENDING_VERIFICATION_PURPOSE:
        return None
    user_id = payload.get("user_id")
    return int(user_id) if user_id else None


def create_otp_login_token(user_id: int) -> str:
    """A short-lived token identifying who an OTP-login OTP was issued to.
    Uses its own purpose (distinct from PENDING_VERIFICATION_PURPOSE) so it
    can't be replayed against the email-verification endpoints, which skip
    OTP checks entirely for already-verified users."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "purpose": OTP_LOGIN_PURPOSE,
        "user_id": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=OTP_LOGIN_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, settings.auth.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_otp_login_token(token: str) -> int | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.auth.jwt_secret, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("purpose") != OTP_LOGIN_PURPOSE:
        return None
    user_id = payload.get("user_id")
    return int(user_id) if user_id else None

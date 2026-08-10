import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from apis.models.session import Session
from apis.models.user import User, UserRole
from apis.security import (
    create_otp_login_token,
    create_pending_verification_token,
    decode_otp_login_token,
    hash_password,
    verify_password,
)
from config import get_settings
from services.crypto.email_crypto import hash_email
from services.database.postgres.connection import get_session
from services.email.email_service import send_login_otp, send_password_reset_link, send_registration_otp
from utils.rate_limiter import RateLimits

from .auth_helper import issue_login, issue_otp, require_pending_user, verify_otp
from .auth_schema import AuthResponse, PendingAuthResponse, RegisterRequest

logger = logging.getLogger(__name__)

# Registration and login OTPs share one field-set on `users`; which flow
# applies is implied by email_verified at issue/verify time.
EMAIL_VERIFICATION_OTP_EXPIRY_MINUTES = 15
RATE_LIMIT_EMAIL_VERIFICATION_MAX_ATTEMPTS = 5
RATE_LIMIT_EMAIL_VERIFICATION_COOLDOWN_MINUTES = 60

LOGIN_OTP_EXPIRY_MINUTES = 5
RATE_LIMIT_LOGIN_OTP_MAX_ATTEMPTS = 5
RATE_LIMIT_LOGIN_OTP_COOLDOWN_MINUTES = 15

RATE_LIMIT_LOGIN_LOCKOUT_MAX_ATTEMPTS = 5
RATE_LIMIT_LOGIN_LOCKOUT_MINUTES = 15

# DB-tracked so a used reset link can be invalidated (a bare JWT can't be).
RESET_TOKEN_EXPIRY_MINUTES = 30
RATE_LIMIT_PASSWORD_RESET_COOLDOWN_SECONDS = 60

INVALID_OTP_LOGIN_SESSION_DETAIL = "Your login session has expired. Please try logging in again."
INVALID_LOGIN_DETAIL = "Invalid email or password."
INVALID_REFRESH_DETAIL = "Your session has expired. Please log in again."


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


def handle_register(data: RegisterRequest, ip_address: str | None) -> PendingAuthResponse:
    if ip_address:
        RateLimits.auth.REGISTER_IP.check(f"register:{ip_address}")

    session = get_session()
    try:
        try:
            user = session.query(User).filter(User.email_hash == hash_email(data.email)).first()
            if user and user.email_verified:
                raise HTTPException(status_code=409, detail="An account with this email already exists.")

            password_hash = hash_password(data.password)
            if user:
                user.name = data.name
                user.password_hash = password_hash
                user.company_name = data.companyName
            else:
                user = User(
                    name=data.name,
                    password_hash=password_hash,
                    company_name=data.companyName,
                    role=UserRole.CUSTOMER.value,
                    email_verified=False,
                )
                user.email = data.email
                session.add(user)
            session.flush()

            _enforce_otp_generation_limits("register", data.email, ip_address)
            otp_code = issue_otp(
                session,
                user,
                EMAIL_VERIFICATION_OTP_EXPIRY_MINUTES,
                RATE_LIMIT_EMAIL_VERIFICATION_MAX_ATTEMPTS,
                RATE_LIMIT_EMAIL_VERIFICATION_COOLDOWN_MINUTES,
            )
            pending_token = create_pending_verification_token(user.id)
            session.commit()
            send_registration_otp(data.email, otp_code)
            return PendingAuthResponse(tempToken=pending_token)
        except IntegrityError:
            raise HTTPException(status_code=409, detail="An account with this email already exists.") from None
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to register user")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_verify_registration_otp(
    pending_token: str, otp: str, device_info: str | None, ip_address: str | None
) -> tuple[AuthResponse, str]:
    session = get_session()
    try:
        user = require_pending_user(session, pending_token)
        if user.email_verified:
            result = issue_login(session, user, device_info, ip_address)
            session.commit()
            return result

        verify_otp(session, user, otp, RATE_LIMIT_EMAIL_VERIFICATION_MAX_ATTEMPTS)
        user.email_verified = True
        result = issue_login(session, user, device_info, ip_address)
        session.commit()
        return result
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to verify registration OTP")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_resend_otp(pending_token: str, ip_address: str | None) -> PendingAuthResponse:
    session = get_session()
    try:
        user = require_pending_user(session, pending_token)
        if user.email_verified:
            raise HTTPException(status_code=409, detail="This account is already verified.")

        _enforce_otp_generation_limits("register", user.email, ip_address)
        otp_code = issue_otp(
            session,
            user,
            EMAIL_VERIFICATION_OTP_EXPIRY_MINUTES,
            RATE_LIMIT_EMAIL_VERIFICATION_MAX_ATTEMPTS,
            RATE_LIMIT_EMAIL_VERIFICATION_COOLDOWN_MINUTES,
        )
        new_pending_token = create_pending_verification_token(user.id)
        session.commit()
        send_registration_otp(user.email, otp_code)
        return PendingAuthResponse(tempToken=new_pending_token)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to resend registration OTP")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_login(
    email: str, password: str, device_info: str | None, ip_address: str | None
) -> tuple[AuthResponse, str]:
    if ip_address:
        RateLimits.auth.LOGIN_IP.check(f"login:{ip_address}")

    session = get_session()
    try:
        user = session.query(User).filter(User.email_hash == hash_email(email)).first()

        if not user or not user.active:
            raise HTTPException(status_code=401, detail=INVALID_LOGIN_DETAIL)
        # Same message whether locked or not - avoids leaking account existence.
        if user.locked_until and user.locked_until > datetime.utcnow():
            raise HTTPException(status_code=401, detail=INVALID_LOGIN_DETAIL)

        if not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= RATE_LIMIT_LOGIN_LOCKOUT_MAX_ATTEMPTS:
                user.locked_until = datetime.utcnow() + timedelta(minutes=RATE_LIMIT_LOGIN_LOCKOUT_MINUTES)
            session.commit()
            raise HTTPException(status_code=401, detail=INVALID_LOGIN_DETAIL)

        user.failed_login_attempts = 0
        user.locked_until = None

        if not user.email_verified:
            # Correct password, unverified - resume signup's OTP flow, no auto-resend.
            pending_token = create_pending_verification_token(user.id)
            session.commit()
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Please verify your email before logging in.",
                    "data": {"tempToken": pending_token},
                },
            )
        result = issue_login(session, user, device_info, ip_address)
        session.commit()
        return result
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to log in user")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_send_login_otp(email: str, ip_address: str | None) -> PendingAuthResponse:
    if ip_address:
        RateLimits.auth.LOGIN_OTP_IP.check(f"login_otp:{ip_address}")

    session = get_session()
    try:
        user = session.query(User).filter(User.email_hash == hash_email(email)).first()
        if not user or not user.active or not user.email_verified:
            raise HTTPException(status_code=401, detail="Invalid email or account not found.")

        _enforce_otp_generation_limits("login", email, ip_address)
        otp_code = issue_otp(
            session,
            user,
            LOGIN_OTP_EXPIRY_MINUTES,
            RATE_LIMIT_LOGIN_OTP_MAX_ATTEMPTS,
            RATE_LIMIT_LOGIN_OTP_COOLDOWN_MINUTES,
        )
        pending_token = create_otp_login_token(user.id)
        session.commit()
        send_login_otp(user.email, otp_code)
        return PendingAuthResponse(tempToken=pending_token)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to send login OTP")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_verify_login_otp(
    pending_token: str, otp: str, device_info: str | None, ip_address: str | None
) -> tuple[AuthResponse, str]:
    user_id = decode_otp_login_token(pending_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail=INVALID_OTP_LOGIN_SESSION_DETAIL)

    session = get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user or not user.active:
            raise HTTPException(status_code=401, detail=INVALID_OTP_LOGIN_SESSION_DETAIL)

        verify_otp(session, user, otp, RATE_LIMIT_LOGIN_OTP_MAX_ATTEMPTS)
        result = issue_login(session, user, device_info, ip_address)
        session.commit()
        return result
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to verify login OTP")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_forgot_password(email: str, ip_address: str | None) -> None:
    if ip_address:
        RateLimits.auth.FORGOT_PASSWORD_IP.check(f"forgot_password:{ip_address}")

    session = get_session()
    try:
        user = session.query(User).filter(User.email_hash == hash_email(email)).first()
        # Same response either way - avoids leaking which emails are registered.
        if user and user.active:
            if (
                user.reset_requested_at
                and (datetime.utcnow() - user.reset_requested_at).total_seconds() < RATE_LIMIT_PASSWORD_RESET_COOLDOWN_SECONDS
            ):
                return
            raw_token = secrets.token_urlsafe(32)
            user.reset_token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            user.reset_token_expire_at = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES)
            user.reset_requested_at = datetime.utcnow()
            session.commit()
            reset_link = f"{get_settings().services.frontend_base_url}/reset-password?token={raw_token}"
            send_password_reset_link(user.email, reset_link)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to process forgot-password request")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_reset_password(token: str, new_password: str) -> None:
    session = get_session()
    try:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        user = session.query(User).filter(User.reset_token_hash == token_hash).first()
        if not user or not user.reset_token_expire_at or user.reset_token_expire_at < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Invalid or expired reset link.")

        user.password_hash = hash_password(new_password)
        # Single-use: nothing left to match against on replay.
        user.reset_token_hash = None
        user.reset_token_expire_at = None
        session.commit()
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to reset password")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_refresh(raw_token: str, device_info: str | None, ip_address: str | None) -> tuple[AuthResponse, str]:
    session = get_session()
    try:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        existing = session.query(Session).filter(Session.refresh_token_hash == token_hash).first()
        if not existing:
            raise HTTPException(status_code=401, detail=INVALID_REFRESH_DETAIL)

        if existing.revoked_at is not None:
            # Reuse of an already-rotated token = likely theft; revoke every session.
            session.query(Session).filter(
                Session.user_id == existing.user_id, Session.revoked_at.is_(None)
            ).update({"revoked_at": datetime.utcnow()})
            session.commit()
            raise HTTPException(status_code=401, detail=INVALID_REFRESH_DETAIL)

        if existing.expires_at < datetime.utcnow():
            raise HTTPException(status_code=401, detail=INVALID_REFRESH_DETAIL)

        user = session.query(User).filter(User.id == existing.user_id).first()
        if not user or not user.active:
            raise HTTPException(status_code=401, detail=INVALID_REFRESH_DETAIL)

        existing.revoked_at = datetime.utcnow()
        result = issue_login(session, user, device_info, ip_address)
        session.commit()
        return result
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to refresh session")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_logout(raw_refresh_token: str | None) -> None:
    if not raw_refresh_token:
        return
    session = get_session()
    try:
        token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        existing = (
            session.query(Session)
            .filter(Session.refresh_token_hash == token_hash, Session.revoked_at.is_(None))
            .first()
        )
        if existing:
            existing.revoked_at = datetime.utcnow()
            session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to process logout")
    finally:
        session.close()

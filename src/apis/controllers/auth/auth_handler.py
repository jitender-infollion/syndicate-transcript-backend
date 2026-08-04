import hashlib
import logging
import math
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from apis.models.session import Session
from apis.models.user import User, UserRole
from apis.security import (
    create_access_token,
    create_otp_login_token,
    create_pending_verification_token,
    decode_otp_login_token,
    decode_pending_verification_token,
    hash_password,
    verify_password,
)
from config import get_settings
from services.crypto.email_crypto import hash_email
from services.crypto.otp_crypto import hash_otp
from services.database.postgres.connection import get_session
from services.email.email_service import send_login_otp, send_password_reset_link, send_registration_otp

from .auth_schema import AuthResponse, AuthUserResponse, PendingAuthResponse, RegisterRequest

logger = logging.getLogger(__name__)

# Per-flow OTP expiry / attempt-limit / post-limit cooldown. Email
# verification codes live longer since users may read the email later; login
# codes are entered right away and get a tighter window. Both flows share one
# field-set on `users` - which flow applies is implied by email_verified at
# issue/verify time (unverified -> signup code, verified -> login code), so
# no separate purpose column is needed.
EMAIL_VERIFICATION_OTP_EXPIRY_MINUTES = 15
EMAIL_VERIFICATION_MAX_OTP_ATTEMPTS = 5
EMAIL_VERIFICATION_OTP_COOLDOWN_MINUTES = 60

LOGIN_OTP_EXPIRY_MINUTES = 5
LOGIN_MAX_OTP_ATTEMPTS = 5
LOGIN_OTP_COOLDOWN_MINUTES = 15

# Password login brute-force lockout.
LOGIN_LOCKOUT_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15

# DB-tracked password reset token (replaces the old stateless-JWT reset link -
# this lets a used link be invalidated, which a bare JWT can't do on its own).
RESET_TOKEN_EXPIRY_MINUTES = 30
RESET_REQUEST_COOLDOWN_SECONDS = 60

INVALID_SESSION_DETAIL = "Your verification session has expired. Please sign in again to resume verification."
INVALID_OTP_LOGIN_SESSION_DETAIL = "Your login session has expired. Please try logging in again."
INVALID_LOGIN_DETAIL = "Invalid email or password."
INVALID_REFRESH_DETAIL = "Your session has expired. Please log in again."


def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _issue_otp(session, user: User, expiry_minutes: int, max_attempts: int, cooldown_minutes: int) -> str:
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

    otp_code = _generate_otp()
    user.otp_hash = hash_otp(otp_code)
    user.otp_expire_time = datetime.utcnow() + timedelta(minutes=expiry_minutes)
    user.otp_retry_count = 0
    return otp_code


def _verify_otp(session, user: User, otp: str, max_attempts: int) -> None:
    if not user.otp_hash or user.otp_expire_time is None:
        raise HTTPException(status_code=400, detail="No OTP found. Please request a new one.")
    if user.otp_expire_time < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
    if user.otp_retry_count >= max_attempts:
        raise HTTPException(status_code=429, detail="Too many incorrect attempts. Please request a new OTP.")
    if hash_otp(otp) != user.otp_hash:
        user.otp_retry_count += 1
        session.commit()
        raise HTTPException(status_code=400, detail="Invalid OTP.")

    # Single-use: nothing left to match against on replay.
    user.otp_hash = None
    user.otp_expire_time = None
    user.otp_retry_count = 0


def _to_auth_response(user: User) -> AuthResponse:
    token = create_access_token(user_id=user.id, user_name=user.name, email=user.email)
    return AuthResponse(
        token=token,
        user=AuthUserResponse(id=str(user.id), name=user.name, email=user.email, companyName=user.company_name),
    )


def _issue_session(session, user: User, device_info: str | None, ip_address: str | None) -> str:
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


def _issue_login(
    session, user: User, device_info: str | None, ip_address: str | None
) -> tuple[AuthResponse, str]:
    auth_response = _to_auth_response(user)
    refresh_token = _issue_session(session, user, device_info, ip_address)
    return auth_response, refresh_token


def _require_pending_user(session, pending_token: str) -> User:
    user_id = decode_pending_verification_token(pending_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail=INVALID_SESSION_DETAIL)
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail=INVALID_SESSION_DETAIL)
    return user


def handle_register(data: RegisterRequest) -> PendingAuthResponse:
    """Stores the full signup record immediately (including the hashed
    password) and sends an OTP. email_verified stays false until
    handle_verify_registration_otp succeeds. Identity for the rest of the
    verification flow is carried by the returned pending token, not by
    resending email/password - so a later login attempt (handle_login) can
    hand out a fresh pending token to resume verification without the
    original signup form data."""
    session = get_session()
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

        otp_code = _issue_otp(
            session,
            user,
            EMAIL_VERIFICATION_OTP_EXPIRY_MINUTES,
            EMAIL_VERIFICATION_MAX_OTP_ATTEMPTS,
            EMAIL_VERIFICATION_OTP_COOLDOWN_MINUTES,
        )
        pending_token = create_pending_verification_token(user.id)
        session.commit()
        send_registration_otp(data.email, otp_code)
        return PendingAuthResponse(tempToken=pending_token)
    except HTTPException:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from None
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
        user = _require_pending_user(session, pending_token)
        if user.email_verified:
            result = _issue_login(session, user, device_info, ip_address)
            session.commit()
            return result

        _verify_otp(session, user, otp, EMAIL_VERIFICATION_MAX_OTP_ATTEMPTS)
        user.email_verified = True
        result = _issue_login(session, user, device_info, ip_address)
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


def handle_resend_otp(pending_token: str) -> PendingAuthResponse:
    session = get_session()
    try:
        user = _require_pending_user(session, pending_token)
        if user.email_verified:
            raise HTTPException(status_code=409, detail="This account is already verified.")

        otp_code = _issue_otp(
            session,
            user,
            EMAIL_VERIFICATION_OTP_EXPIRY_MINUTES,
            EMAIL_VERIFICATION_MAX_OTP_ATTEMPTS,
            EMAIL_VERIFICATION_OTP_COOLDOWN_MINUTES,
        )
        new_pending_token = create_pending_verification_token(user.id)
        session.commit()
        send_registration_otp(user.email, otp_code)
        return PendingAuthResponse(tempToken=new_pending_token)
    except HTTPException:
        session.rollback()
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
    session = get_session()
    try:
        user = session.query(User).filter(User.email_hash == hash_email(email)).first()

        if not user or not user.active:
            raise HTTPException(status_code=401, detail=INVALID_LOGIN_DETAIL)
        # Same generic message whether locked or not - revealing lockout state
        # distinctly would tell an attacker an account exists just from
        # hitting the endpoint, no password knowledge required.
        if user.locked_until and user.locked_until > datetime.utcnow():
            raise HTTPException(status_code=401, detail=INVALID_LOGIN_DETAIL)

        if not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= LOGIN_LOCKOUT_MAX_ATTEMPTS:
                user.locked_until = datetime.utcnow() + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
            session.commit()
            raise HTTPException(status_code=401, detail=INVALID_LOGIN_DETAIL)

        user.failed_login_attempts = 0
        user.locked_until = None

        if not user.email_verified:
            # Credentials are correct but the account is unverified - hand back
            # a fresh pending token so the frontend can resume the same OTP
            # verification flow used at signup, without a new OTP being sent
            # unless the user explicitly asks to resend.
            pending_token = create_pending_verification_token(user.id)
            session.commit()
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Please verify your email before logging in.",
                    "data": {"tempToken": pending_token},
                },
            )
        result = _issue_login(session, user, device_info, ip_address)
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


def handle_send_login_otp(email: str) -> PendingAuthResponse:
    session = get_session()
    try:
        user = session.query(User).filter(User.email_hash == hash_email(email)).first()
        if not user or not user.active or not user.email_verified:
            raise HTTPException(status_code=401, detail="Invalid email or account not found.")

        otp_code = _issue_otp(
            session,
            user,
            LOGIN_OTP_EXPIRY_MINUTES,
            LOGIN_MAX_OTP_ATTEMPTS,
            LOGIN_OTP_COOLDOWN_MINUTES,
        )
        pending_token = create_otp_login_token(user.id)
        session.commit()
        send_login_otp(user.email, otp_code)
        return PendingAuthResponse(tempToken=pending_token)
    except HTTPException:
        session.rollback()
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

        _verify_otp(session, user, otp, LOGIN_MAX_OTP_ATTEMPTS)
        result = _issue_login(session, user, device_info, ip_address)
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


def handle_forgot_password(email: str) -> None:
    session = get_session()
    try:
        user = session.query(User).filter(User.email_hash == hash_email(email)).first()
        # Always behave the same whether or not the account exists, to avoid
        # leaking which emails are registered.
        if user and user.active:
            if (
                user.reset_requested_at
                and (datetime.utcnow() - user.reset_requested_at).total_seconds() < RESET_REQUEST_COOLDOWN_SECONDS
            ):
                return
            raw_token = secrets.token_urlsafe(32)
            user.reset_token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            user.reset_token_expire_at = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES)
            user.reset_requested_at = datetime.utcnow()
            session.commit()
            reset_link = f"{get_settings().services.frontend_base_url}/reset-password?token={raw_token}"
            send_password_reset_link(user.email, reset_link)
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
        session.rollback()
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
            # Reuse of an already-rotated-out token - likely theft. Revoke
            # every other active session for this user as a precaution.
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
        result = _issue_login(session, user, device_info, ip_address)
        session.commit()
        return result
    except HTTPException:
        session.rollback()
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

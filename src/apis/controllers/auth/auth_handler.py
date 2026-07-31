import logging
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from apis.models.otp import Otp
from apis.models.user import User, UserRole
from apis.security import (
    create_access_token,
    create_password_reset_token,
    create_pending_verification_token,
    decode_password_reset_token,
    decode_pending_verification_token,
    hash_password,
    verify_password,
)
from config import get_settings
from services.database.postgres.connection import get_session
from services.email.email_service import send_password_reset_link, send_registration_otp

from .auth_schema import AuthResponse, AuthUserResponse, PendingAuthResponse, RegisterRequest

logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES = 10
MAX_OTP_ATTEMPTS = 5

INVALID_SESSION_DETAIL = "Your verification session has expired. Please sign in again to resume verification."


def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _issue_otp(session, user: User) -> str:
    otp_code = _generate_otp()
    session.add(
        Otp(
            user_id=user.id,
            otp=otp_code,
            expire_time=datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES),
            retry_count=0,
        )
    )
    return otp_code


def _to_auth_response(user: User) -> AuthResponse:
    token = create_access_token(user_id=user.id, user_name=user.name, email=user.email)
    return AuthResponse(
        token=token,
        user=AuthUserResponse(id=str(user.id), name=user.name, email=user.email, companyName=user.company_name),
    )


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
        user = session.query(User).filter(User.email == data.email).first()
        if user and user.email_verified:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")

        password_hash = hash_password(data.password)
        if user:
            user.name = data.name
            user.password = password_hash
            user.company_name = data.companyName
        else:
            user = User(
                email=data.email,
                name=data.name,
                password=password_hash,
                company_name=data.companyName,
                role=UserRole.CUSTOMER.value,
                email_verified=False,
            )
            session.add(user)
        session.flush()

        otp_code = _issue_otp(session, user)
        pending_token = create_pending_verification_token(user.id)
        session.commit()
        send_registration_otp(data.email, otp_code)
        return PendingAuthResponse(pendingToken=pending_token)
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


def handle_verify_registration_otp(pending_token: str, otp: str) -> AuthResponse:
    session = get_session()
    try:
        user = _require_pending_user(session, pending_token)
        if user.email_verified:
            return _to_auth_response(user)

        otp_row = session.query(Otp).filter(Otp.user_id == user.id).order_by(Otp.id.desc()).first()
        if not otp_row:
            raise HTTPException(status_code=400, detail="No OTP found. Please request a new one.")
        if otp_row.expire_time < datetime.utcnow():
            raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
        if otp_row.retry_count >= MAX_OTP_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Too many incorrect attempts. Please request a new OTP.")
        if otp_row.otp != otp:
            otp_row.retry_count += 1
            session.commit()
            raise HTTPException(status_code=400, detail="Invalid OTP.")

        user.email_verified = True
        session.delete(otp_row)
        session.commit()
        return _to_auth_response(user)
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

        otp_code = _issue_otp(session, user)
        new_pending_token = create_pending_verification_token(user.id)
        session.commit()
        send_registration_otp(user.email, otp_code)
        return PendingAuthResponse(pendingToken=new_pending_token)
    except HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to resend registration OTP")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_login(email: str, password: str) -> AuthResponse:
    session = get_session()
    try:
        user = session.query(User).filter(User.email == email).first()
        if not user or not user.active or not verify_password(password, user.password):
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        if not user.email_verified:
            # Credentials are correct but the account is unverified - hand back
            # a fresh pending token so the frontend can resume the same OTP
            # verification flow used at signup, without a new OTP being sent
            # unless the user explicitly asks to resend.
            pending_token = create_pending_verification_token(user.id)
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Please verify your email before logging in.",
                    "data": {"pendingToken": pending_token},
                },
            )
        return _to_auth_response(user)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to log in user")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_forgot_password(email: str) -> None:
    session = get_session()
    try:
        user = session.query(User).filter(User.email == email).first()
        # Always behave the same whether or not the account exists, to avoid
        # leaking which emails are registered.
        if user and user.active:
            reset_token = create_password_reset_token(user.id)
            reset_link = f"{get_settings().services.frontend_base_url}/reset-password?token={reset_token}"
            send_password_reset_link(email, reset_link)
    except Exception:
        logger.exception("Failed to process forgot-password request")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_reset_password(token: str, new_password: str) -> None:
    user_id = decode_password_reset_token(token)
    if user_id is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")

    session = get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired reset link.")
        user.password = hash_password(new_password)
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


def handle_logout(user_id: int) -> None:
    # Stateless JWT, no server-side session to invalidate yet. Present so the
    # frontend's forward-looking POST /api/auth/logout call has somewhere to
    # land; revisit with a token-blacklist table if real invalidation becomes
    # a requirement.
    logger.info("User %s logged out", user_id)

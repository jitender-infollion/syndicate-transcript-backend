import logging
import smtplib
from email.message import EmailMessage

from config import get_settings

logger = logging.getLogger(__name__)


def _send_email(to_email: str, subject: str, body: str) -> None:
    email_config = get_settings().email
    if not email_config.is_configured:
        logger.warning("SMTP is not configured; logging email instead of sending. To: %s | %s", to_email, body)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = email_config.from_email
    message["To"] = to_email
    message.set_content(body)

    try:
        if email_config.use_tls:
            with smtplib.SMTP(email_config.smtp_host, email_config.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(email_config.smtp_username, email_config.smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP_SSL(email_config.smtp_host, email_config.smtp_port, timeout=10) as server:
                server.login(email_config.smtp_username, email_config.smtp_password)
                server.send_message(message)
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        raise


def send_registration_otp(email: str, otp: str) -> None:
    _send_email(
        to_email=email,
        subject="Your verification code",
        body=f"Your OTP is {otp}. It expires in 10 minutes.",
    )


def send_password_reset_link(email: str, reset_link: str) -> None:
    _send_email(
        to_email=email,
        subject="Reset your password",
        body=f"Click the link below to reset your password:\n\n{reset_link}",
    )

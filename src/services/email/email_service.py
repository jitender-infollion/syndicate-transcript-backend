import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import get_settings

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=select_autoescape(["html"]))

OTP_TTL_MINUTES = 10


def _render_otp_email(title: str, heading: str, description: str, otp: str) -> str:
    return _jinja_env.get_template("otp_code.html").render(
        title=title,
        render_logo=False,
        logo_url=None,
        heading=heading,
        description=description,
        code=otp,
        ttl_minutes=OTP_TTL_MINUTES,
    )


def _send_email(to_email: str, subject: str, body: str, html: str | None = None) -> None:
    email_config = get_settings().email
    if not email_config.is_configured:
        logger.warning("SMTP is not configured; logging email instead of sending. To: %s | %s", to_email, body)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = email_config.from_email
    message["To"] = to_email
    message.set_content(body)
    if html:
        message.add_alternative(html, subtype="html")

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
    html = _render_otp_email(
        title="Your Infollion verification code",
        heading="Verify your email",
        description="Enter this code to verify your email and finish creating your account:",
        otp=otp,
    )
    _send_email(
        to_email=email,
        subject="Your verification code",
        body=f"Your OTP is {otp}. It expires in {OTP_TTL_MINUTES} minutes.",
        html=html,
    )


def send_login_otp(email: str, otp: str) -> None:
    html = _render_otp_email(
        title="Your Infollion login code",
        heading="Your login code",
        description="Enter this code to log in to Infollion:",
        otp=otp,
    )
    _send_email(
        to_email=email,
        subject="Your login code",
        body=f"Your login OTP is {otp}. It expires in {OTP_TTL_MINUTES} minutes.",
        html=html,
    )


def send_password_reset_link(email: str, reset_link: str) -> None:
    _send_email(
        to_email=email,
        subject="Reset your password",
        body=f"Click the link below to reset your password:\n\n{reset_link}",
    )

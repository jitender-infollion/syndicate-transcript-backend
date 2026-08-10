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

# Publicly-reachable URL, not derived from frontend_base_url (unreachable from an email client in dev).
_LOGO_URL = "https://www.infollion.com/imported/logo-new.png"


def _render_otp_email(title: str, heading: str, description: str, otp: str) -> str:
    return _jinja_env.get_template("otp_code.html").render(
        title=title,
        render_logo=True,
        logo_url=_LOGO_URL,
        heading=heading,
        description=description,
        code=otp,
        ttl_minutes=OTP_TTL_MINUTES,
    )


def _send_email(
    to_email: str,
    subject: str,
    body: str,
    html: str | None = None,
    attachment_bytes: bytes | None = None,
    attachment_filename: str | None = None,
) -> None:
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
    if attachment_bytes and attachment_filename:
        message.add_attachment(attachment_bytes, maintype="application", subtype="pdf", filename=attachment_filename)

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


def send_invoice_email(email: str, name: str | None, invoice_number: str, pdf_bytes: bytes) -> None:
    html = _jinja_env.get_template("invoice_email.html").render(
        title="Your Infollion receipt",
        logo_url=_LOGO_URL,
        name=name,
        invoice_number=invoice_number,
    )
    _send_email(
        to_email=email,
        subject=f"Your Infollion receipt - {invoice_number}",
        body=f"Thanks for your purchase! Your receipt ({invoice_number}) is attached.",
        html=html,
        attachment_bytes=pdf_bytes,
        attachment_filename=f"{invoice_number}.pdf",
    )

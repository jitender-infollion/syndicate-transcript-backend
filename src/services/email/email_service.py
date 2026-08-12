import base64
import logging
from pathlib import Path

import httpx
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
        logger.warning("SendGrid is not configured; logging email instead of sending. To: %s | %s", to_email, body)
        return

    content = [{"type": "text/plain", "value": body}]
    if html:
        content.append({"type": "text/html", "value": html})

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": email_config.from_email},
        "subject": subject,
        "content": content,
    }
    if attachment_bytes and attachment_filename:
        payload["attachments"] = [
            {
                "content": base64.b64encode(attachment_bytes).decode(),
                "filename": attachment_filename,
                "type": "application/pdf",
                "disposition": "attachment",
            }
        ]

    try:
        # SendGrid sends over HTTPS (443), not SMTP - some hosts (e.g. Render)
        # block outbound SMTP entirely, which is why this uses their HTTP API.
        response = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {email_config.sendgrid_api_key}"},
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
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

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import get_settings

_TEMPLATES_DIR = Path(__file__).parent / "templates"
# Autoescape on, same as the email templates - user-controlled fields (name,
# company_name) must never be interpreted as HTML.
_jinja_env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=select_autoescape(["html"]))

_COMPANY_NAME = "Infollion Research Services"
_COMPANY_TAGLINE = "On-Demand Experts"
_COMPANY_ADDRESS_LINES = ["5th Floor, UNITECH CYBER PARK, Durga Colony, Sector 39", "Gurugram, Haryana 122003"]
_COMPANY_PHONE = "0124 440 6555"
# Same logo already used in the invoice email template, for consistent branding.
_LOGO_URL = "https://www.infollion.com/imported/logo-new.png"


def generate_receipt_pdf(order, item_rows, user, invoice_number: str) -> bytes:
    # Imported lazily: WeasyPrint's native deps (Pango/Cairo/GObject) aren't
    # always available in every environment this module gets imported into
    # (e.g. a local dev machine without them set up) - importing here means
    # only an actual receipt-generation call fails, not the whole app's startup.
    from weasyprint import HTML

    paid_at = order.paid_at or order.created_at

    # Qty is always 1 - each item row is one transcript purchase, never a
    # multi-quantity line.
    items = [{"description": topic or "Untitled transcript", "qty": 1, "amount": price} for price, topic in item_rows]

    template = _jinja_env.get_template("receipt.html")
    html = template.render(
        company_name=_COMPANY_NAME,
        company_tagline=_COMPANY_TAGLINE,
        company_address_lines=_COMPANY_ADDRESS_LINES,
        company_phone=_COMPANY_PHONE,
        logo_url=_LOGO_URL,
        date=paid_at.strftime("%d %b %Y"),
        invoice_number=invoice_number,
        customer_id=user.id,
        bill_to_name=user.name or "-",
        bill_to_email=user.email,
        bill_to_company=user.company_name,
        items=items,
        currency=order.currency,
        subtotal=order.amount,
        total=order.amount,
        support_email=get_settings().email.from_email,
    )
    return HTML(string=html, base_url=str(_TEMPLATES_DIR)).write_pdf()

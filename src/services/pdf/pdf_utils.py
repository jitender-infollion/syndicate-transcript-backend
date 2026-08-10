import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate

BODY_TEXT_COLOR = colors.HexColor("#374151")


def make_document(title: str, margin_inches: float) -> tuple[SimpleDocTemplate, io.BytesIO]:
    buffer = io.BytesIO()
    margin = margin_inches * inch
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        title=title,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )
    return doc, buffer


def build_pdf(doc: SimpleDocTemplate, buffer: io.BytesIO, elements: list) -> bytes:
    doc.build(elements)
    return buffer.getvalue()

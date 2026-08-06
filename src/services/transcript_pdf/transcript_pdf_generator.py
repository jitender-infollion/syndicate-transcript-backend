import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def generate_transcript_pdf(transcript, full_text: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        title=transcript.topic or "Transcript",
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Heading1"], fontSize=18)
    body_style = ParagraphStyle(
        "body", parent=styles["Normal"], fontSize=10, leading=16, textColor=colors.HexColor("#374151")
    )

    elements = [Paragraph(escape(transcript.topic or "Untitled transcript"), title_style), Spacer(1, 0.3 * inch)]
    for line in full_text.split("\n"):
        if line.strip():
            elements.append(Paragraph(escape(line), body_style))
            elements.append(Spacer(1, 0.1 * inch))

    doc.build(elements)
    return buffer.getvalue()

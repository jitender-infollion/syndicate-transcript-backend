from xml.sax.saxutils import escape

from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Spacer

from services.pdf import BODY_TEXT_COLOR, build_pdf, make_document


def generate_transcript_pdf(transcript, full_text: str) -> bytes:
    doc, buffer = make_document(transcript.topic or "Transcript", margin_inches=0.75)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Heading1"], fontSize=18)
    body_style = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=16, textColor=BODY_TEXT_COLOR)

    elements = [Paragraph(escape(transcript.topic or "Untitled transcript"), title_style), Spacer(1, 0.3 * inch)]
    for line in full_text.split("\n"):
        if line.strip():
            elements.append(Paragraph(escape(line), body_style))
            elements.append(Spacer(1, 0.1 * inch))

    return build_pdf(doc, buffer, elements)

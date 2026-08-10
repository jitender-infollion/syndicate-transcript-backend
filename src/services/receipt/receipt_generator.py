from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

from config import get_settings
from services.pdf import BODY_TEXT_COLOR, build_pdf, make_document

_LOGO_PATH = Path(__file__).parent / "assets" / "infollion_logo_square.png"


def generate_receipt_pdf(order, item_rows, user, invoice_number: str) -> bytes:
    doc, buffer = make_document(f"Receipt {order.id}", margin_inches=0.6)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9, leading=14, textColor=BODY_TEXT_COLOR)
    section_heading = ParagraphStyle(
        "sectionHeading", parent=styles["Normal"], fontSize=9, leading=14, textColor=colors.HexColor("#111827"),
        fontName="Helvetica-Bold", spaceAfter=4,
    )

    elements = []
    paid_at = order.paid_at or order.created_at

    # Header: logo + "Infollion" (left) / "PAYMENT RECEIPT" + invoice meta (right)
    logo_cell = Image(str(_LOGO_PATH), width=0.9 * inch, height=0.9 * inch) if _LOGO_PATH.exists() else ""
    company_name = Paragraph("<b>Infollion</b>", ParagraphStyle("company", parent=styles["Normal"], fontSize=16))
    left_block = Table([[logo_cell, company_name]], colWidths=[1 * inch, 2.5 * inch])
    left_block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))

    receipt_title = Paragraph(
        "PAYMENT RECEIPT",
        ParagraphStyle("title", parent=styles["Normal"], fontSize=18, alignment=2, textColor=colors.HexColor("#111827")),
    )
    meta = Paragraph(
        "<br/>".join(
            [
                f"<b>Date:</b> {paid_at.strftime('%d %b %Y')}",
                f"<b>Invoice No:</b> {invoice_number}",
                f"<b>Customer ID:</b> {user.id}",
            ]
        ),
        ParagraphStyle("meta", parent=styles["Normal"], fontSize=9, alignment=2, leading=14, textColor=colors.HexColor("#4b5563")),
    )
    right_block = Table([[receipt_title], [Spacer(1, 4)], [meta]], colWidths=[3 * inch])
    right_block.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT")]))

    header_table = Table([[left_block, right_block]], colWidths=[3.6 * inch, 3.3 * inch])
    header_table.setStyle(
        TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)])
    )
    elements.append(header_table)
    elements.append(Spacer(1, 0.3 * inch))

    # User-controlled fields must be escaped - Paragraph parses its input as mini-XML.
    elements.append(Paragraph("BILL TO", section_heading))
    bill_lines = [user.name or "-", user.email]
    if user.company_name:
        bill_lines.append(user.company_name)
    for line in bill_lines:
        elements.append(Paragraph(escape(line), body))
    elements.append(Spacer(1, 0.25 * inch))

    table_data = [["Description", "Qty", "Amount"]]
    for price, topic in item_rows:
        table_data.append([topic or "Untitled transcript", "1", f"{order.currency} {price}"])
    items_table = Table(table_data, colWidths=[4.2 * inch, 0.8 * inch, 1.9 * inch])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(items_table)
    elements.append(Spacer(1, 0.1 * inch))

    # Totals - no tax/discount lines: neither exists in this system yet.
    totals_table = Table(
        [["Subtotal", f"{order.currency} {order.amount}"], ["Total Paid", f"{order.currency} {order.amount}"]],
        colWidths=[5 * inch, 1.9 * inch],
    )
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, -1), (-1, -1), 11),
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
                ("TOPPADDING", (0, -1), (-1, -1), 6),
            ]
        )
    )
    elements.append(totals_table)
    elements.append(Spacer(1, 0.3 * inch))

    # "Download transcript" is forward-looking - that endpoint still returns 501.
    elements.append(Paragraph("LICENSE", section_heading))
    for line in [
        "&bull; Full transcript view access",
        "&bull; Personal use only - do not redistribute",
        "&bull; Download transcript",
    ]:
        elements.append(Paragraph(line, body))
    elements.append(Spacer(1, 0.4 * inch))

    from_email = get_settings().email.from_email
    if from_email:
        elements.append(Paragraph(f"Questions about this receipt? Contact {from_email}.", body))
    elements.append(Paragraph("<b>Thank you for your purchase!</b>", body))

    return build_pdf(doc, buffer, elements)

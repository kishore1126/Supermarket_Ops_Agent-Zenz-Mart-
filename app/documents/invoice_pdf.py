"""ReportLab GST Tax Invoice PDF Generator."""

import os
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config import settings


def generate_invoice_pdf(
    bill_data: dict,
    shop_info: dict | None = None,
    output_path: str | Path | None = None,
) -> str:
    """
    Generate a professional Indian GST Tax Invoice PDF using ReportLab.
    
    bill_data: dict from preview_bill / finalize_bill containing items, taxes, round_off, total.
    shop_info: dict containing shop_name, shop_gstin, shop_address, shop_phone.
    output_path: optional target path for PDF file.
    """
    shop = {
        "name": (shop_info and shop_info.get("shop_name")) or settings.DEFAULT_SHOP_NAME,
        "gstin": (shop_info and shop_info.get("shop_gstin")) or settings.DEFAULT_SHOP_GSTIN,
        "address": (shop_info and shop_info.get("shop_address")) or settings.DEFAULT_SHOP_ADDRESS,
        "phone": (shop_info and shop_info.get("shop_phone")) or settings.DEFAULT_SHOP_PHONE,
    }

    bill_id = bill_data.get("bill_id", 0)
    if output_path is None:
        target_file = settings.get_invoice_path(f"invoice_{bill_id:04d}.pdf")
    else:
        target_file = Path(output_path)
        target_file.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(target_file),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        "ShopTitle",
        parent=styles["Heading1"],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#1e293b"),
        fontName="Helvetica-Bold",
        alignment=0,
    )
    meta_style = ParagraphStyle(
        "ShopMeta",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#475569"),
        fontName="Helvetica",
    )
    badge_style = ParagraphStyle(
        "InvoiceBadge",
        parent=styles["Heading2"],
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0f766e"),
        fontName="Helvetica-Bold",
        alignment=2,
    )
    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        fontName="Helvetica",
    )
    cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        fontName="Helvetica-Bold",
    )
    cell_right = ParagraphStyle(
        "TableCellRight",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        fontName="Helvetica",
        alignment=2,
    )
    cell_right_bold = ParagraphStyle(
        "TableCellRightBold",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        fontName="Helvetica-Bold",
        alignment=2,
    )

    elements = []

    # 1. Header Section
    header_data = [
        [
            Paragraph(f"<b>{shop['name']}</b>", title_style),
            Paragraph("TAX INVOICE<br/><font size=8 color='#64748b'>Original for Recipient</font>", badge_style),
        ],
        [
            Paragraph(
                f"GSTIN: <b>{shop['gstin']}</b><br/>"
                f"{shop['address']}<br/>"
                f"Phone: {shop['phone']}",
                meta_style,
            ),
            Paragraph(
                f"<b>Invoice #:</b> INV-{bill_id:04d}<br/>"
                f"<b>Date:</b> {bill_data.get('created_at', '')[:10]}<br/>"
                f"<b>Payment:</b> {bill_data.get('payment_method', 'UPI')}<br/>"
                f"<b>Status:</b> <font color='#059669'><b>{bill_data.get('status', 'FINALIZED')}</b></font>",
                ParagraphStyle("InvMetaRight", parent=meta_style, alignment=2),
            ),
        ],
    ]
    header_table = Table(header_data, colWidths=[3.2 * inch, 3.8 * inch])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 8))

    # Divider line
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=8))

    # 2. Billed To Customer Section
    cust_name = bill_data.get("customer_name") or "Walk-in Customer"
    cust_phone = bill_data.get("customer_phone") or "—"
    cust_info = [
        [
            Paragraph("<b>Billed To:</b>", cell_bold),
            Paragraph(f"{cust_name} (Phone: {cust_phone})", cell_style),
            Paragraph(f"<b>Place of Supply:</b> Intra-State (State Code: {shop['gstin'][:2]})", cell_right),
        ]
    ]
    cust_table = Table(cust_info, colWidths=[1.0 * inch, 3.2 * inch, 2.8 * inch])
    cust_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(cust_table)
    elements.append(Spacer(1, 6))

    # 3. Line Items Table
    # Columns: S.No | Description | HSN | Qty | Rate | Taxable (₹) | CGST (₹) | SGST (₹) | Total (₹)
    table_data = [
        [
            Paragraph("<b>#</b>", cell_bold),
            Paragraph("<b>Item Description</b>", cell_bold),
            Paragraph("<b>HSN</b>", cell_bold),
            Paragraph("<b>Qty</b>", cell_bold),
            Paragraph("<b>Rate (₹)</b>", cell_right_bold),
            Paragraph("<b>Taxable (₹)</b>", cell_right_bold),
            Paragraph("<b>CGST (₹)</b>", cell_right_bold),
            Paragraph("<b>SGST (₹)</b>", cell_right_bold),
            Paragraph("<b>Total (₹)</b>", cell_right_bold),
        ]
    ]

    for idx, item in enumerate(bill_data.get("items", []), start=1):
        table_data.append([
            Paragraph(str(idx), cell_style),
            Paragraph(f"<b>{item['product_name']}</b>", cell_style),
            Paragraph(str(item.get("hsn_code", "0000")), cell_style),
            Paragraph(f"{item['quantity']} {item.get('unit', '')}", cell_style),
            Paragraph(f"{item['unit_price']:.2f}", cell_right),
            Paragraph(f"{item.get('taxable_value', 0.0):.2f}", cell_right),
            Paragraph(f"{item.get('cgst_amount', 0.0):.2f}<br/><font size=6 color='#64748b'>({int(item.get('gst_rate', 0)*50)}%)</font>", cell_right),
            Paragraph(f"{item.get('sgst_amount', 0.0):.2f}<br/><font size=6 color='#64748b'>({int(item.get('gst_rate', 0)*50)}%)</font>", cell_right),
            Paragraph(f"<b>{item.get('line_total', 0.0):.2f}</b>", cell_right),
        ])

    col_widths = [0.3 * inch, 2.1 * inch, 0.65 * inch, 0.75 * inch, 0.7 * inch, 0.75 * inch, 0.6 * inch, 0.6 * inch, 0.75 * inch]
    items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("ALIGN", (0, 0), (3, -1), "LEFT"),
        ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 8))

    # 4. Summary & Round Off Box (Point 3)
    subtotal = bill_data.get("subtotal", 0.0)
    cgst_total = bill_data.get("cgst", 0.0)
    sgst_total = bill_data.get("sgst", 0.0)
    round_off = bill_data.get("round_off", 0.0)
    final_total = bill_data.get("total", 0.0)

    round_off_sign = f"+₹{round_off:.2f}" if round_off >= 0 else f"-₹{abs(round_off):.2f}"

    summary_data = [
        [
            Paragraph("<b>Taxable Subtotal:</b>", cell_style),
            Paragraph(f"₹{subtotal:.2f}", cell_right),
        ],
        [
            Paragraph("<b>Total Central GST (CGST):</b>", cell_style),
            Paragraph(f"₹{cgst_total:.2f}", cell_right),
        ],
        [
            Paragraph("<b>Total State GST (SGST):</b>", cell_style),
            Paragraph(f"₹{sgst_total:.2f}", cell_right),
        ],
        [
            Paragraph("<b>Round Off Adjustment:</b>", cell_style),
            Paragraph(round_off_sign, cell_right),
        ],
        [
            Paragraph("<b>Grand Total (Payable):</b>", ParagraphStyle("GrandTotalLabel", parent=cell_bold, fontSize=10, textColor=colors.HexColor("#0f766e"))),
            Paragraph(f"<b>₹{final_total:.2f}</b>", ParagraphStyle("GrandTotalVal", parent=cell_right_bold, fontSize=11, textColor=colors.HexColor("#0f766e"))),
        ],
    ]

    summary_table = Table(summary_data, colWidths=[2.2 * inch, 1.3 * inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0fdf4")),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, colors.HexColor("#0f766e")),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#0f766e")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    # Place summary on the right side
    terms_text = Paragraph(
        "<b>Terms & Conditions:</b><br/>"
        "1. Goods once sold will not be taken back without bill.<br/>"
        "2. All disputes subject to local jurisdiction.<br/>"
        "<i>Thank you for supporting your local Kirana!</i>",
        ParagraphStyle("Terms", parent=styles["Normal"], fontSize=7, leading=9, textColor=colors.HexColor("#64748b")),
    )

    bottom_block = Table(
        [[terms_text, summary_table]],
        colWidths=[3.5 * inch, 3.5 * inch]
    )
    bottom_block.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(KeepTogether([bottom_block]))
    elements.append(Spacer(1, 14))

    # 5. Signatory Block
    sig_data = [
        [
            Paragraph(f"E. & O.E.", ParagraphStyle("Eoe", parent=styles["Normal"], fontSize=7, textColor=colors.HexColor("#94a3b8"))),
            Paragraph(f"For <b>{shop['name']}</b><br/><br/><br/>Authorized Signatory", ParagraphStyle("Sign", parent=styles["Normal"], fontSize=8, alignment=2)),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[3.5 * inch, 3.5 * inch])
    elements.append(sig_table)

    # Build PDF
    doc.build(elements)
    return str(target_file)

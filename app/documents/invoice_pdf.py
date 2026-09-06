"""ReportLab Modern Minimalist GST Invoice PDF Generator — Matching Zenz Mart Aesthetic."""

from datetime import datetime, timezone
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


# Design Palette (Geo/Zenz Modern Minimalist Aesthetic)
CYAN_ACCENT = colors.HexColor("#00C2E8")
CYAN_LIGHT = colors.HexColor("#F0FAFC")
DARK_SLATE = colors.HexColor("#0F172A")
MEDIUM_SLATE = colors.HexColor("#334155")
LIGHT_MUTED = colors.HexColor("#64748B")
BORDER_GREY = colors.HexColor("#E2E8F0")
CARD_BG = colors.HexColor("#F8FAFC")
WHITE = colors.HexColor("#FFFFFF")


def generate_invoice_pdf(
    bill_data: dict,
    shop_info: dict | None = None,
    output_path: str | Path | None = None,
) -> str:
    """
    Generate a high-aesthetic, modern GST Tax Invoice PDF matching Zenz Mart style.
    
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
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()

    # Typography
    brand_style = ParagraphStyle(
        "BrandTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=DARK_SLATE,
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "BrandSubtitle",
        parent=styles["Normal"],
        fontSize=7.5,
        leading=10,
        textColor=LIGHT_MUTED,
        fontName="Helvetica",
    )
    meta_label = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
        textColor=CYAN_ACCENT,
        fontName="Helvetica-Bold",
    )
    meta_val = ParagraphStyle(
        "MetaVal",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        textColor=DARK_SLATE,
        fontName="Helvetica-Bold",
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        textColor=DARK_SLATE,
        fontName="Helvetica-Bold",
    )
    qty_style = ParagraphStyle(
        "QtyStyle",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=12,
        textColor=CYAN_ACCENT,
        fontName="Helvetica-Bold",
    )
    item_desc_style = ParagraphStyle(
        "ItemDescStyle",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=DARK_SLATE,
        fontName="Helvetica",
    )
    item_meta_style = ParagraphStyle(
        "ItemMetaStyle",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
        textColor=LIGHT_MUTED,
        fontName="Helvetica",
    )
    price_style = ParagraphStyle(
        "PriceStyle",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=12,
        textColor=DARK_SLATE,
        fontName="Helvetica-Bold",
        alignment=2,
    )
    summary_label = ParagraphStyle(
        "SummaryLabel",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=12,
        textColor=LIGHT_MUTED,
        fontName="Helvetica",
    )
    summary_val = ParagraphStyle(
        "SummaryVal",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=12,
        textColor=DARK_SLATE,
        fontName="Helvetica-Bold",
        alignment=2,
    )
    total_label_style = ParagraphStyle(
        "TotalLabel",
        parent=styles["Normal"],
        fontSize=13,
        leading=16,
        textColor=CYAN_ACCENT,
        fontName="Helvetica-Bold",
    )
    total_val_style = ParagraphStyle(
        "TotalVal",
        parent=styles["Normal"],
        fontSize=14,
        leading=17,
        textColor=CYAN_ACCENT,
        fontName="Helvetica-Bold",
        alignment=2,
    )
    thank_you_style = ParagraphStyle(
        "ThankYou",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        textColor=DARK_SLATE,
        fontName="Helvetica-Bold",
        alignment=1,
    )
    badge_btn_style = ParagraphStyle(
        "BadgeBtn",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=10,
        textColor=WHITE,
        fontName="Helvetica-Bold",
        alignment=1,
    )
    pill_text = ParagraphStyle(
        "PillText",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
        textColor=LIGHT_MUTED,
        fontName="Helvetica",
        alignment=1,
    )

    elements = []

    # 1. Top Dual-Tone Accent Bar (Left 70% Cyan, Right 30% Dark Slate)
    bar_data = [["", ""]]
    bar_table = Table(bar_data, colWidths=[5.0 * inch, 2.0 * inch], rowHeights=[3.5])
    bar_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), CYAN_ACCENT),
        ("BACKGROUND", (1, 0), (1, 0), MEDIUM_SLATE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(bar_table)
    elements.append(Spacer(1, 14))

    # 2. Store Branding Header
    elements.append(Paragraph(shop["name"].upper(), brand_style))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph("MODERN GROCERY EXPERIENCE", subtitle_style))
    elements.append(Spacer(1, 14))

    # Parse date and time
    created_at_str = bill_data.get("created_at", "")
    try:
        dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        date_display = dt.strftime("%b %d").upper()
        time_display = dt.strftime("%H:%M")
    except Exception:
        date_display = datetime.now().strftime("%b %d").upper()
        time_display = datetime.now().strftime("%H:%M")

    # 3. Metadata 3-Cards (DATE, TIME, REGISTER/BILL#)
    card1 = [
        [Paragraph("DATE", meta_label)],
        [Paragraph(date_display, meta_val)],
    ]
    card2 = [
        [Paragraph("TIME", meta_label)],
        [Paragraph(time_display, meta_val)],
    ]
    card3 = [
        [Paragraph("REGISTER", meta_label)],
        [Paragraph(f"#{bill_id:02d}" if bill_id < 100 else f"#{bill_id}", meta_val)],
    ]

    t1 = Table(card1, colWidths=[2.2 * inch])
    t1.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("LINELEFT", (0, 0), (0, -1), 2.5, CYAN_ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))

    t2 = Table(card2, colWidths=[2.2 * inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("LINELEFT", (0, 0), (0, -1), 2.5, CYAN_ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))

    t3 = Table(card3, colWidths=[2.2 * inch])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("LINELEFT", (0, 0), (0, -1), 2.5, CYAN_ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))

    meta_row = Table([[t1, t2, t3]], colWidths=[2.33 * inch, 2.33 * inch, 2.34 * inch])
    meta_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(meta_row)
    elements.append(Spacer(1, 16))

    # 4. Items Section Heading
    sec_data = [[
        Paragraph("ITEMS", section_heading),
        HRFlowable(width="100%", thickness=0.8, color=BORDER_GREY, spaceAfter=0)
    ]]
    sec_table = Table(sec_data, colWidths=[0.8 * inch, 6.2 * inch])
    sec_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(sec_table)
    elements.append(Spacer(1, 6))

    # 5. Line Items Table
    items = bill_data.get("items", [])
    item_rows = []
    for idx, item in enumerate(items):
        q_val = item["quantity"]
        q_str = f"{int(q_val)}" if q_val == int(q_val) else f"{q_val}"
        
        # Product name and optional GST details
        p_name = item["product_name"]
        gst_pct = int(item.get("gst_rate", 0) * 100)
        hsn = item.get("hsn_code", "0000")
        meta_sub = f"<font size=6.5 color='#94a3b8'>HSN {hsn} • GST {gst_pct}%</font>"
        
        desc_para = Paragraph(f"<b>{p_name}</b><br/>{meta_sub}", item_desc_style)
        qty_para = Paragraph(q_str, qty_style)
        price_para = Paragraph(f"₹{item.get('line_total', 0.0):.2f}", price_style)
        
        item_rows.append([qty_para, desc_para, price_para])

    items_table = Table(item_rows, colWidths=[0.5 * inch, 5.2 * inch, 1.3 * inch])
    items_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 14))

    # 6. Summary & Totals Box
    subtotal = bill_data.get("subtotal", 0.0)
    cgst = bill_data.get("cgst", 0.0)
    sgst = bill_data.get("sgst", 0.0)
    total_tax = round(cgst + sgst, 2)
    round_off = bill_data.get("round_off", 0.0)
    final_total = bill_data.get("total", 0.0)

    round_sign = f"+₹{round_off:.2f}" if round_off >= 0 else f"-₹{abs(round_off):.2f}"

    summary_rows = [
        [
            Paragraph("Subtotal", summary_label),
            Paragraph(f"₹{subtotal:.2f}", summary_val),
        ],
        [
            Paragraph("Tax (GST Breakup: CGST + SGST)", summary_label),
            Paragraph(f"₹{total_tax:.2f}", summary_val),
        ],
        [
            Paragraph("Round Off Adjustment", summary_label),
            Paragraph(round_sign, summary_val),
        ],
        [
            HRFlowable(width="100%", thickness=1.5, color=CYAN_ACCENT, spaceAfter=2, spaceBefore=2),
            HRFlowable(width="100%", thickness=1.5, color=CYAN_ACCENT, spaceAfter=2, spaceBefore=2),
        ],
        [
            Paragraph("TOTAL", total_label_style),
            Paragraph(f"₹{final_total:.2f}", total_val_style),
        ],
    ]

    summary_card = Table(summary_rows, colWidths=[5.2 * inch, 1.5 * inch])
    summary_card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    elements.append(KeepTogether([summary_card]))
    elements.append(Spacer(1, 12))

    # 7. Payment Info Block
    pay_method = bill_data.get("payment_method", "UPI").upper()
    pay_data = [
        [
            Paragraph("PAYMENT METHOD", ParagraphStyle("P1", parent=summary_label, fontSize=7.5)),
            Paragraph(pay_method, ParagraphStyle("P2", parent=summary_val, fontSize=8.5, textColor=DARK_SLATE)),
        ],
        [
            Paragraph("AMOUNT PAID", ParagraphStyle("P3", parent=summary_label, fontSize=7.5)),
            Paragraph(f"₹{final_total:.2f}", ParagraphStyle("P4", parent=summary_val, fontSize=8.5, textColor=DARK_SLATE)),
        ],
    ]
    pay_table = Table(pay_data, colWidths=[4.8 * inch, 1.9 * inch])
    pay_table.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEABOVE", (0, 0), (-1, 0), 0.6, BORDER_GREY),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, BORDER_GREY),
    ]))
    elements.append(KeepTogether([pay_table]))
    elements.append(Spacer(1, 20))

    # 8. Thank You Header
    elements.append(Paragraph("THANK YOU FOR SHOPPING", thank_you_style))
    elements.append(Spacer(1, 8))

    # 9. Cyan Badge Button (ZENZ MART)
    btn_data = [[Paragraph(shop["name"].upper(), badge_btn_style)]]
    btn_table = Table(btn_data, colWidths=[1.8 * inch], rowHeights=[22])
    btn_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CYAN_ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    # Center the button table
    center_btn = Table([[btn_table]], colWidths=[7.0 * inch])
    center_btn.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.6 * inch),
    ]))
    elements.append(center_btn)
    elements.append(Spacer(1, 14))

    # 10. Footer Pills (Returns, Store Hours, Contact)
    p1 = Table([[Paragraph("Returns: 30 days", pill_text)]], colWidths=[2.1 * inch], rowHeights=[20])
    p1.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    p2 = Table([[Paragraph("Store Hours: 8AM - 10PM", pill_text)]], colWidths=[2.2 * inch], rowHeights=[20])
    p2.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    p3 = Table([[Paragraph(f"Contact: {shop['phone']}", pill_text)]], colWidths=[2.2 * inch], rowHeights=[20])
    p3.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    pills_row = Table([[p1, p2, p3]], colWidths=[2.25 * inch, 2.35 * inch, 2.35 * inch])
    pills_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    elements.append(pills_row)
    elements.append(Spacer(1, 10))

    # Sub-footer tagline
    tagline = Paragraph(
        f"{shop['name'].upper()} • MODERN GROCERY EXPERIENCE • GSTIN: {shop['gstin']} • EST. 2026",
        ParagraphStyle("SubFooter", parent=styles["Normal"], fontSize=6.5, textColor=LIGHT_MUTED, alignment=1),
    )
    elements.append(tagline)

    # Build PDF
    doc.build(elements)
    return str(target_file)

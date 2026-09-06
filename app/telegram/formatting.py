"""Telegram Formatting & Inline Keyboard Builders with Monospace Tables and Emoji Icons."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def format_bill_receipt(bill_data: dict) -> str:
    """Format bill line items and tax breakdown in a monospace tabular layout."""
    bill_id = bill_data.get("bill_id", 0)
    status = bill_data.get("status", "DRAFT")
    customer = bill_data.get("customer_name") or "Walk-in Customer"
    payment = bill_data.get("payment_method", "UPI")

    status_icon = "🧾" if status == "DRAFT" else "✅"
    lines = [
        f"{status_icon} *Bill #{bill_id:04d}* — `{status}`",
        f"👤 Customer: *{customer}* | 💳 Payment: *{payment}*",
        "",
        "```",
        f"{'Item':<18} {'Qty':<6} {'Rate':>6} {'Total':>8}",
        "-" * 40,
    ]

    for item in bill_data.get("items", []):
        name = item["product_name"][:16]
        qty_str = f"{item['quantity']}{item.get('unit', 'pk')[:2]}"
        rate_str = f"₹{item['unit_price']:.0f}"
        total_str = f"₹{item.get('line_total', 0):.2f}"
        lines.append(f"{name:<18} {qty_str:<6} {rate_str:>6} {total_str:>8}")

    lines.append("-" * 40)
    subtotal = bill_data.get("subtotal", 0.0)
    cgst = bill_data.get("cgst", 0.0)
    sgst = bill_data.get("sgst", 0.0)
    round_off = bill_data.get("round_off", 0.0)
    total = bill_data.get("total", 0.0)

    round_sign = f"+₹{round_off:.2f}" if round_off >= 0 else f"-₹{abs(round_off):.2f}"

    lines.append(f"{'Taxable Subtotal:':<26} {'₹' + f'{subtotal:.2f}':>13}")
    lines.append(f"{'CGST (Central Tax):':<26} {'₹' + f'{cgst:.2f}':>13}")
    lines.append(f"{'SGST (State Tax):':<26} {'₹' + f'{sgst:.2f}':>13}")
    lines.append(f"{'Round Off:':<26} {round_sign:>13}")
    lines.append("=" * 40)
    lines.append(f"{'GRAND TOTAL:':<26} {'₹' + f'{total:.2f}':>13}")
    lines.append("```")

    if status == "DRAFT":
        lines.append("\n👉 *Tap below to Confirm or Cancel this bill:*")
    return "\n".join(lines)


def format_daily_close_message(close_data: dict) -> str:
    """Format daily store closing metrics into monospace tables."""
    date_str = close_data.get("date", "")
    total_sales = close_data.get("total_sales", 0.0)
    bills = close_data.get("total_bills", 0)
    avg_ticket = close_data.get("avg_bill_value", 0.0)
    total_tax = close_data.get("total_tax", 0.0)
    pay = close_data.get("payment_breakdown", {})

    upi_str = f"₹{pay.get('UPI', 0.0):.2f}"
    cash_str = f"₹{pay.get('CASH', 0.0):.2f}"
    card_str = f"₹{pay.get('CARD', 0.0):.2f}"
    khata_str = f"₹{pay.get('KHATA', 0.0):.2f}"
    sales_str = f"₹{total_sales:.2f}"
    avg_str = f"₹{avg_ticket:.2f}"
    tax_str = f"₹{total_tax:.2f}"

    lines = [
        f"📊 *DAILY STORE CLOSE — {date_str}*",
        "",
        "```",
        f"{'Metric':<24} {'Value':>14}",
        "-" * 40,
        f"{'Total Revenue:':<24} {sales_str:>14}",
        f"{'Total Invoices Cut:':<24} {str(bills):>14}",
        f"{'Average Ticket Size:':<24} {avg_str:>14}",
        f"{'Total GST Collected:':<24} {tax_str:>14}",
        "-" * 40,
        "PAYMENT BREAKDOWN:",
        f"  • UPI:                 {upi_str:>14}",
        f"  • Cash:                {cash_str:>14}",
        f"  • Card:                {card_str:>14}",
        f"  • Khata (Credit):      {khata_str:>14}",
        "```",
    ]

    top_items = close_data.get("top_items", [])
    if top_items:
        lines.append("\n🏆 *Top Selling SKUs Today:*")
        lines.append("```")
        lines.append(f"{'Product':<20} {'Qty':<6} {'Revenue':>10}")
        lines.append("-" * 38)
        for itm in top_items:
            p_name = itm["product_name"][:18]
            q_str = f"{itm['quantity_sold']}{itm.get('unit', '')[:2]}"
            r_str = f"₹{itm['revenue']:.0f}"
            lines.append(f"{p_name:<20} {q_str:<6} {r_str:>10}")
        lines.append("```")

    return "\n".join(lines)


def get_bill_preview_keyboard(bill_id: int) -> InlineKeyboardMarkup:
    """Create inline keyboard with Confirm and Cancel buttons for bill drafts."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm & Finalize", callback_data=f"finalize_bill_{bill_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_bill_{bill_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_bill_finalized_keyboard(bill_id: int) -> InlineKeyboardMarkup:
    """Create inline keyboard with Download Invoice PDF button."""
    keyboard = [
        [
            InlineKeyboardButton("📄 Download Invoice PDF", callback_data=f"download_pdf_{bill_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

"""Deterministic GST & Round-Off Calculator for Indian Retail Supermarket."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


def round_cur(val: float | Decimal) -> float:
    """Round currency value to 2 decimal places using standard half-up rounding."""
    d = Decimal(str(val)) if not isinstance(val, Decimal) else val
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass
class ItemGSTBreakup:
    product_name: str
    unit: str
    quantity: float
    unit_price: float
    gst_rate: float
    hsn_code: str
    line_total: float       # Gross inclusive amount
    taxable_value: float    # Base price excluding tax
    cgst_amount: float      # Central GST (50% of tax)
    sgst_amount: float      # State GST (50% of tax)
    tax_amount: float       # Total GST amount


@dataclass
class InvoiceGSTSummary:
    items: list[ItemGSTBreakup]
    subtotal: float         # Sum of taxable values
    total_cgst: float       # Sum of CGST
    total_sgst: float       # Sum of SGST
    total_tax: float        # Sum of CGST + SGST
    raw_total: float        # subtotal + total_tax
    round_off: float        # Difference to nearest integer Rupee
    final_total: float      # Final rounded payable amount
    slab_summary: dict[float, dict[str, float]]  # {rate: {taxable, cgst, sgst, total}}


def calculate_item_gst(
    product_name: str,
    unit: str,
    quantity: float,
    unit_price: float,
    gst_rate: float,
    hsn_code: str = "0000",
) -> ItemGSTBreakup:
    """
    Calculate GST for a single line item based on tax-inclusive retail price (MRP).
    
    Formula:
      Gross = round(quantity * unit_price, 2)
      Taxable Base = round(Gross / (1 + gst_rate), 2)
      Total Tax = round(Gross - Taxable Base, 2)
      CGST = round(Total Tax / 2, 2)
      SGST = round(Total Tax - CGST, 2)  [Guarantees CGST + SGST == Total Tax]
    """
    gross = round_cur(quantity * unit_price)
    
    if gst_rate <= 0.0:
        return ItemGSTBreakup(
            product_name=product_name,
            unit=unit,
            quantity=quantity,
            unit_price=unit_price,
            gst_rate=0.0,
            hsn_code=hsn_code,
            line_total=gross,
            taxable_value=gross,
            cgst_amount=0.0,
            sgst_amount=0.0,
            tax_amount=0.0,
        )

    # Decompose tax-inclusive gross
    dec_gross = Decimal(str(gross))
    dec_rate = Decimal(str(gst_rate))
    dec_one_plus_rate = Decimal("1.0") + dec_rate

    dec_taxable = (dec_gross / dec_one_plus_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    dec_tax = dec_gross - dec_taxable

    dec_cgst = (dec_tax / Decimal("2.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    dec_sgst = dec_tax - dec_cgst  # Guarantees zero 1-paisa leak

    return ItemGSTBreakup(
        product_name=product_name,
        unit=unit,
        quantity=quantity,
        unit_price=unit_price,
        gst_rate=gst_rate,
        hsn_code=hsn_code,
        line_total=float(dec_gross),
        taxable_value=float(dec_taxable),
        cgst_amount=float(dec_cgst),
        sgst_amount=float(dec_sgst),
        tax_amount=float(dec_tax),
    )


def calculate_invoice_gst(
    items_data: list[dict],
) -> InvoiceGSTSummary:
    """
    Calculate full invoice GST breakdown, slab grouping, and integer rupee round-off.
    
    items_data: list of dicts with:
      name, unit, quantity, unit_price, gst_rate, hsn_code
    """
    calculated_items: list[ItemGSTBreakup] = []
    slab_summary: dict[float, dict[str, float]] = {}

    subtotal = Decimal("0.00")
    total_cgst = Decimal("0.00")
    total_sgst = Decimal("0.00")

    for item in items_data:
        breakup = calculate_item_gst(
            product_name=item["name"],
            unit=item.get("unit", "packet"),
            quantity=float(item["quantity"]),
            unit_price=float(item["unit_price"]),
            gst_rate=float(item.get("gst_rate", 0.0)),
            hsn_code=str(item.get("hsn_code", "0000")),
        )
        calculated_items.append(breakup)

        subtotal += Decimal(str(breakup.taxable_value))
        total_cgst += Decimal(str(breakup.cgst_amount))
        total_sgst += Decimal(str(breakup.sgst_amount))

        rate_pct = round(breakup.gst_rate * 100, 1)
        if rate_pct not in slab_summary:
            slab_summary[rate_pct] = {"taxable": 0.0, "cgst": 0.0, "sgst": 0.0, "total_tax": 0.0}
        
        slab_summary[rate_pct]["taxable"] = round_cur(slab_summary[rate_pct]["taxable"] + breakup.taxable_value)
        slab_summary[rate_pct]["cgst"] = round_cur(slab_summary[rate_pct]["cgst"] + breakup.cgst_amount)
        slab_summary[rate_pct]["sgst"] = round_cur(slab_summary[rate_pct]["sgst"] + breakup.sgst_amount)
        slab_summary[rate_pct]["total_tax"] = round_cur(slab_summary[rate_pct]["total_tax"] + breakup.tax_amount)

    raw_total = subtotal + total_cgst + total_sgst
    # Final total rounded to nearest integer Rupee
    final_total = Decimal(str(round(float(raw_total))))
    round_off = (final_total - raw_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return InvoiceGSTSummary(
        items=calculated_items,
        subtotal=float(subtotal),
        total_cgst=float(total_cgst),
        total_sgst=float(total_sgst),
        total_tax=float(total_cgst + total_sgst),
        raw_total=float(raw_total),
        round_off=float(round_off),
        final_total=float(final_total),
        slab_summary=slab_summary,
    )

"""Unit tests for GST math, tax slabs, and round-off calculation."""

from app.billing.gst import calculate_item_gst, calculate_invoice_gst


def test_zero_gst_staple():
    """Test 0% GST calculation for loose staples (e.g. Loose Sugar)."""
    # 2kg Loose Sugar at ₹44.00/kg = ₹88.00 gross
    item = calculate_item_gst(
        product_name="Loose Sugar",
        unit="kg",
        quantity=2.0,
        unit_price=44.0,
        gst_rate=0.0,
        hsn_code="1701",
    )
    assert item.line_total == 88.0
    assert item.taxable_value == 88.0
    assert item.cgst_amount == 0.0
    assert item.sgst_amount == 0.0
    assert item.tax_amount == 0.0


def test_five_percent_packaged_staple():
    """Test 5% GST calculation for packaged staples (e.g. Aashirvaad Atta 5kg)."""
    # 1 packet of Aashirvaad Atta 5kg at ₹245.00 (tax-inclusive)
    # Taxable Base = 245 / 1.05 = 233.33
    # Total Tax = 245 - 233.33 = 11.67
    # CGST = 5.84, SGST = 5.83
    item = calculate_item_gst(
        product_name="Aashirvaad Atta 5kg",
        unit="packet",
        quantity=1.0,
        unit_price=245.0,
        gst_rate=0.05,
        hsn_code="1101",
    )
    assert item.line_total == 245.0
    assert item.taxable_value == 233.33
    assert item.tax_amount == 11.67
    assert item.cgst_amount == 5.84
    assert item.sgst_amount == 5.83
    assert round(item.cgst_amount + item.sgst_amount, 2) == item.tax_amount


def test_twelve_percent_fmcg():
    """Test 12% GST calculation for packaged FMCG (e.g. Maggi 70g)."""
    # 4 packets Maggi at ₹14.00 = ₹56.00 gross
    # Taxable Base = 56 / 1.12 = 50.00
    # Total Tax = 6.00
    # CGST = 3.00, SGST = 3.00
    item = calculate_item_gst(
        product_name="Maggi 70g",
        unit="packet",
        quantity=4.0,
        unit_price=14.0,
        gst_rate=0.12,
        hsn_code="1902",
    )
    assert item.line_total == 56.0
    assert item.taxable_value == 50.0
    assert item.cgst_amount == 3.0
    assert item.sgst_amount == 3.0
    assert item.tax_amount == 6.0


def test_invoice_gst_summary_and_round_off():
    """Test multi-item invoice aggregation and explicit paise round-off line."""
    items = [
        {"name": "Loose Sugar", "unit": "kg", "quantity": 2, "unit_price": 44.0, "gst_rate": 0.0, "hsn_code": "1701"},
        {"name": "Aashirvaad Atta 5kg", "unit": "packet", "quantity": 1, "unit_price": 245.0, "gst_rate": 0.05, "hsn_code": "1101"},
        {"name": "Maggi 70g", "unit": "packet", "quantity": 4, "unit_price": 14.0, "gst_rate": 0.12, "hsn_code": "1902"},
        {"name": "Amul Butter 100g", "unit": "packet", "quantity": 1, "unit_price": 58.0, "gst_rate": 0.12, "hsn_code": "0405"},
    ]
    summary = calculate_invoice_gst(items)

    # Gross: 88 + 245 + 56 + 58 = 447.00
    assert summary.raw_total == 447.0
    assert summary.final_total == 447.0
    assert summary.round_off == 0.0
    assert len(summary.items) == 4
    assert 0.0 in summary.slab_summary
    assert 5.0 in summary.slab_summary
    assert 12.0 in summary.slab_summary

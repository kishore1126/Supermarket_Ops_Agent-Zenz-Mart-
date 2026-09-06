"""Unit tests for ReportLab Invoice PDF Generator."""

import os
from pathlib import Path
import pytest
from app.documents.invoice_pdf import generate_invoice_pdf


def test_generate_invoice_pdf(tmp_path):
    bill_data = {
        "bill_id": 101,
        "status": "FINALIZED",
        "customer_name": "Ramesh Kumar",
        "customer_phone": "+91 98230 11223",
        "payment_method": "UPI",
        "created_at": "2026-09-06T12:00:00",
        "subtotal": 393.33,
        "cgst": 11.84,
        "sgst": 11.83,
        "total_tax": 23.67,
        "round_off": 0.0,
        "total": 417.0,
        "items": [
            {
                "product_name": "Aashirvaad Atta 5kg",
                "quantity": 1,
                "unit": "packet",
                "unit_price": 245.0,
                "gst_rate": 0.05,
                "hsn_code": "1101",
                "taxable_value": 233.33,
                "cgst_amount": 5.84,
                "sgst_amount": 5.83,
                "line_total": 245.0,
            },
            {
                "product_name": "Loose Sugar",
                "quantity": 2,
                "unit": "kg",
                "unit_price": 44.0,
                "gst_rate": 0.0,
                "hsn_code": "1701",
                "taxable_value": 88.0,
                "cgst_amount": 0.0,
                "sgst_amount": 0.0,
                "line_total": 88.0,
            },
            {
                "product_name": "Maggi 70g",
                "quantity": 6,
                "unit": "packet",
                "unit_price": 14.0,
                "gst_rate": 0.12,
                "hsn_code": "1902",
                "taxable_value": 75.0,
                "cgst_amount": 4.5,
                "sgst_amount": 4.5,
                "line_total": 84.0,
            },
        ],
    }

    target_pdf = tmp_path / "test_invoice.pdf"
    pdf_path = generate_invoice_pdf(bill_data, output_path=target_pdf)

    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 1000  # Valid non-empty PDF

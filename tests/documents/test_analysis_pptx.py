"""Unit tests for PowerPoint Analysis Deck Generator."""

import os
from pathlib import Path
from app.documents.analysis_pptx import generate_analysis_deck


def test_generate_analysis_deck(tmp_path):
    sales_data = {
        "period_days": 7,
        "total_revenue": 14500.0,
        "total_bills": 38,
        "daily_trends": [
            {"date": "2026-08-31", "revenue": 1800.0, "bills": 5},
            {"date": "2026-09-01", "revenue": 2200.0, "bills": 6},
            {"date": "2026-09-02", "revenue": 1950.0, "bills": 4},
            {"date": "2026-09-03", "revenue": 2400.0, "bills": 7},
            {"date": "2026-09-04", "revenue": 2100.0, "bills": 5},
            {"date": "2026-09-05", "revenue": 2650.0, "bills": 6},
            {"date": "2026-09-06", "revenue": 1400.0, "bills": 5},
        ],
        "top_products": [
            {"name": "Aashirvaad Atta 5kg", "revenue": 4900.0, "quantity_sold": 20},
            {"name": "Fortune Sunflower Oil 1L", "revenue": 2900.0, "quantity_sold": 20},
            {"name": "Maggi 70g", "revenue": 2100.0, "quantity_sold": 150},
            {"name": "Amul Butter 100g", "revenue": 1740.0, "quantity_sold": 30},
            {"name": "Surf Excel Quick Wash 1kg", "revenue": 1550.0, "quantity_sold": 10},
        ],
        "payment_methods": {
            "UPI": 9500.0,
            "CASH": 3800.0,
            "CARD": 1200.0,
        },
    }

    low_stock_items = [
        {"name": "Surf Excel Quick Wash 1kg", "stock_qty": 2.0, "reorder_level": 5.0},
    ]

    target_pptx = tmp_path / "test_deck.pptx"
    pptx_path = generate_analysis_deck(
        sales_data=sales_data,
        low_stock_items=low_stock_items,
        output_path=target_pptx,
    )

    assert os.path.exists(pptx_path)
    assert os.path.getsize(pptx_path) > 5000  # Valid presentation file with slides and images

"""Unit Tests for Analytics Feature: Daily Close & Sales Analysis."""

import pytest
from app.billing import service as billing_service
from app.analytics import service as analytics_service
from app.agent.tool_registry import registry
import app.analytics.tools


@pytest.mark.asyncio
async def test_daily_close_empty(seeded_session):
    res = await analytics_service.get_daily_close(seeded_session)
    assert res["total_bills"] == 0
    assert res["total_sales"] == 0.0
    assert res["payment_breakdown"]["UPI"] == 0.0


@pytest.mark.asyncio
async def test_daily_close_with_finalized_sales(seeded_session):
    # Bill 1: UPI payment
    bill1 = await billing_service.start_or_update_bill(
        session=seeded_session,
        items=[
            {"name": "Aashirvaad Atta 5kg", "quantity": 2.0},  # 2 * 245 = 490
            {"name": "Maggi 70g", "quantity": 5.0},            # 5 * 14 = 70
        ],
        payment_method="UPI",
    )
    await billing_service.finalize_bill(seeded_session, bill_id=bill1["bill_id"])

    # Bill 2: Cash payment
    bill2 = await billing_service.start_or_update_bill(
        session=seeded_session,
        items=[
            {"name": "Tata Salt 1kg", "quantity": 2.0},        # 2 * 28 = 56
            {"name": "Loose Sugar", "quantity": 1.0},          # 1 * 44 = 44
        ],
        payment_method="Cash",
    )
    await billing_service.finalize_bill(seeded_session, bill_id=bill2["bill_id"])

    # Compute daily close
    close_data = await analytics_service.get_daily_close(seeded_session)

    assert close_data["total_bills"] == 2
    # Bill 1: 560, Bill 2: 100 -> Total = 660.0
    assert close_data["total_sales"] == 660.0
    assert close_data["payment_breakdown"]["UPI"] == 560.0
    assert close_data["payment_breakdown"]["CASH"] == 100.0
    assert close_data["total_tax"] > 0
    assert len(close_data["top_items"]) >= 2
    assert close_data["top_items"][0]["product_name"] == "Aashirvaad Atta 5kg"


@pytest.mark.asyncio
async def test_sales_analysis_7_days(seeded_session):
    # Create bill
    bill = await billing_service.start_or_update_bill(
        session=seeded_session,
        items=[{"name": "Fortune Sunflower Oil 1L", "quantity": 2.0}],
        payment_method="UPI",
    )
    await billing_service.finalize_bill(seeded_session, bill_id=bill["bill_id"])

    analysis = await analytics_service.get_sales_analysis(seeded_session, days=7)
    assert analysis["total_bills"] >= 1
    assert analysis["total_revenue"] >= 290.0  # 2 * 145 = 290
    assert len(analysis["daily_trends"]) >= 1
    assert len(analysis["top_products"]) >= 1


@pytest.mark.asyncio
async def test_analytics_tool_registry(seeded_session):
    res = await registry.execute(
        name="get_daily_close",
        session=seeded_session,
        arguments={},
    )
    assert "error" not in res
    assert "total_sales" in res

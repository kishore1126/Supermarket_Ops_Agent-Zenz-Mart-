"""Unit Tests for Billing Feature: Multi-turn edits, stock integrity, and oversell guard."""

import pytest
from app.core.errors import (
    BillAlreadyFinalizedError,
    InsufficientStockError,
    ProductNotFoundError,
)
from app.billing import service
from app.inventory.service import check_stock


@pytest.mark.asyncio
async def test_start_bill_and_multi_turn_edit(seeded_session):
    # Step 1: "make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, 1 Amul butter, UPI"
    initial_items = [
        {"name": "Loose Sugar", "quantity": 2.0},
        {"name": "Aashirvaad Atta 5kg", "quantity": 1.0},
        {"name": "Maggi 70g", "quantity": 4.0},
        {"name": "Amul Butter 100g", "quantity": 1.0},
    ]
    preview = await service.start_or_update_bill(
        session=seeded_session,
        items=initial_items,
        payment_method="UPI",
    )
    assert preview["item_count"] == 4
    assert preview["payment_method"] == "UPI"
    assert preview["total"] == 447.0

    # Verify inventory was NOT touched on draft
    maggi_stock = await check_stock(seeded_session, query="Maggi 70g")
    assert maggi_stock[0]["stock_qty"] == 150.0

    # Step 2: "drop the butter, make it 6 Maggi"
    edit_items = [
        {"name": "Amul Butter 100g", "quantity": 0.0},  # drop
        {"name": "Maggi 70g", "quantity": 6.0},         # update qty
    ]
    updated_preview = await service.start_or_update_bill(
        session=seeded_session,
        items=edit_items,
        bill_id=preview["bill_id"],
    )
    assert updated_preview["item_count"] == 3
    # 2kg Sugar (88) + 1 Atta (245) + 6 Maggi (84) = 417.00
    assert updated_preview["total"] == 417.0

    # Step 3: Finalize bill
    finalize_res = await service.finalize_bill(
        session=seeded_session,
        bill_id=preview["bill_id"],
    )
    assert finalize_res["success"] is True
    assert finalize_res["status"] == "FINALIZED"

    # Verify stock decrement
    maggi_stock_after = await check_stock(seeded_session, query="Maggi 70g")
    assert maggi_stock_after[0]["stock_qty"] == 144.0  # 150 - 6

    sugar_stock_after = await check_stock(seeded_session, query="Loose Sugar")
    assert sugar_stock_after[0]["stock_qty"] == 78.0   # 80 - 2


@pytest.mark.asyncio
async def test_oversell_guard_rejection(seeded_session):
    # Try billing 200 Maggi when only 150 are in stock
    preview = await service.start_or_update_bill(
        session=seeded_session,
        items=[{"name": "Maggi 70g", "quantity": 200.0}],
    )
    assert preview["item_count"] == 1

    # Finalize must reject with InsufficientStockError
    with pytest.raises(InsufficientStockError) as exc_info:
        await service.finalize_bill(
            session=seeded_session,
            bill_id=preview["bill_id"],
        )
    assert "Maggi 70g" in str(exc_info.value)

    # Verify stock remains untouched at 150
    maggi_stock = await check_stock(seeded_session, query="Maggi 70g")
    assert maggi_stock[0]["stock_qty"] == 150.0


@pytest.mark.asyncio
async def test_double_finalize_guard(seeded_session):
    preview = await service.start_or_update_bill(
        session=seeded_session,
        items=[{"name": "Tata Salt 1kg", "quantity": 2.0}],
    )
    # First finalize
    await service.finalize_bill(seeded_session, bill_id=preview["bill_id"])

    # Second finalize attempt must fail
    with pytest.raises(BillAlreadyFinalizedError):
        await service.finalize_bill(seeded_session, bill_id=preview["bill_id"])


@pytest.mark.asyncio
async def test_billing_tools_registry(seeded_session):
    from app.agent.tool_registry import registry
    import app.billing.tools

    # Start bill via tool registry
    start_res = await registry.execute(
        name="start_or_update_bill",
        session=seeded_session,
        arguments={
            "items": [{"product_name": "Tata Salt 1kg", "quantity": 3}],
            "payment_method": "Cash",
        },
    )
    assert "error" not in start_res
    assert start_res["total"] == 84.0  # 3 * 28

    # Preview bill via tool registry
    prev_res = await registry.execute(
        name="preview_bill",
        session=seeded_session,
        arguments={"bill_id": start_res["bill_id"]},
    )
    assert "error" not in prev_res
    assert prev_res["item_count"] == 1

    # Finalize bill via tool registry
    fin_res = await registry.execute(
        name="finalize_bill",
        session=seeded_session,
        arguments={"bill_id": start_res["bill_id"]},
    )
    assert "error" not in fin_res
    assert fin_res["success"] is True

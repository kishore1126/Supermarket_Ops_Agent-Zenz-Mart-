"""Unit Tests for Inventory Feature & Tools."""

import pytest
from app.core.errors import BelowCostError, ProductNotFoundError, InvalidOperationError
from app.inventory import service
from app.agent.tool_registry import registry
import app.inventory.tools  # Register tools


@pytest.mark.asyncio
async def test_check_stock_search(seeded_session):
    results = await service.check_stock(seeded_session, query="maggi")
    assert len(results) == 1
    assert results[0]["name"] == "Maggi 70g"
    assert results[0]["stock_qty"] == 150.0
    assert results[0]["gst_rate"] == 0.12


@pytest.mark.asyncio
async def test_receive_stock_success(seeded_session):
    res = await service.receive_stock(
        session=seeded_session,
        product_name="Maggi 70g",
        quantity=50.0,
        cost_price=12.5,
        mrp=14.0,
    )
    assert res["success"] is True
    assert res["current_stock"] == 200.0
    assert res["previous_stock"] == 150.0

    # Verify query
    stock_info = await service.check_stock(seeded_session, query="Maggi 70g")
    assert stock_info[0]["stock_qty"] == 200.0
    assert stock_info[0]["cost_price"] == 12.5


@pytest.mark.asyncio
async def test_add_product_below_cost_guard(seeded_session):
    # Selling ₹10 when cost is ₹15 should fail by default
    with pytest.raises(BelowCostError):
        await service.add_product(
            session=seeded_session,
            name="Discounted Soap",
            unit="piece",
            cost_price=15.0,
            selling_price=10.0,
            mrp=18.0,
            allow_below_cost=False,
        )


@pytest.mark.asyncio
async def test_add_product_below_cost_override(seeded_session):
    # With explicit confirmation, selling below cost succeeds
    res = await service.add_product(
        session=seeded_session,
        name="Clearance Biscuit",
        unit="packet",
        cost_price=20.0,
        selling_price=15.0,
        mrp=25.0,
        allow_below_cost=True,
    )
    assert res["success"] is True
    assert res["selling_price"] == 15.0


@pytest.mark.asyncio
async def test_receive_stock_below_cost_guard(seeded_session):
    # Updating cost to ₹20 when selling price is ₹14 should raise BelowCostError
    with pytest.raises(BelowCostError):
        await service.receive_stock(
            session=seeded_session,
            product_name="Maggi 70g",
            quantity=10,
            cost_price=20.0,
            allow_below_cost=False,
        )


@pytest.mark.asyncio
async def test_get_low_stock(seeded_session):
    # Artificially set stock below reorder level
    prod = await service.get_product_by_name(seeded_session, "Surf Excel Quick Wash 1kg")
    prod.stock_qty = 2.0  # reorder level is 5.0
    await seeded_session.commit()

    low_items = await service.get_low_stock(seeded_session)
    low_names = [item["name"] for item in low_items]
    assert "Surf Excel Quick Wash 1kg" in low_names


@pytest.mark.asyncio
async def test_inventory_tool_execution(seeded_session):
    # Test tool invocation via tool registry
    res = await registry.execute(
        name="check_stock",
        session=seeded_session,
        arguments={"query": "Aashirvaad"},
    )
    assert "error" not in res
    assert res["count"] >= 1
    assert "Aashirvaad Atta 5kg" in [p["name"] for p in res["products"]]

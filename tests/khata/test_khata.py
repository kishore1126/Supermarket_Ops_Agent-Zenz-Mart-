"""Unit Tests for Khata Feature & Ledger Math."""

import pytest
from app.core.errors import CustomerNotFoundError, InvalidOperationError
from app.khata import service
from app.agent.tool_registry import registry
import app.khata.tools


@pytest.mark.asyncio
async def test_get_existing_customer_balance(seeded_session):
    # Ramesh has opening credit of ₹500.00 from seed
    res = await service.get_balance(seeded_session, customer_name="Ramesh Kumar")
    assert res["customer_name"] == "Ramesh Kumar"
    assert res["current_balance"] == 500.0


@pytest.mark.asyncio
async def test_add_credit_and_payment_cycle(seeded_session):
    # Step 1: "put ₹500 on Ramesh's credit"
    credit_res = await service.add_credit(
        session=seeded_session,
        customer_name="Ramesh Kumar",
        amount=500.0,
        note="Monthly ration",
    )
    assert credit_res["success"] is True
    assert credit_res["current_balance"] == 1000.0  # 500 + 500

    # Step 2: "Ramesh paid ₹300"
    payment_res = await service.record_payment(
        session=seeded_session,
        customer_name="Ramesh Kumar",
        amount=300.0,
        note="GPay transfer",
    )
    assert payment_res["success"] is True
    assert payment_res["current_balance"] == 700.0  # 1000 - 300
    assert payment_res["is_cleared"] is False

    # Step 3: Full settlement
    settle_res = await service.record_payment(
        session=seeded_session,
        customer_name="Ramesh Kumar",
        amount=700.0,
        note="Cash settlement",
    )
    assert settle_res["success"] is True
    assert settle_res["current_balance"] == 0.0
    assert settle_res["is_cleared"] is True


@pytest.mark.asyncio
async def test_payment_unknown_customer(seeded_session):
    with pytest.raises(CustomerNotFoundError):
        await service.record_payment(
            session=seeded_session,
            customer_name="NonExistentPerson",
            amount=200.0,
        )


@pytest.mark.asyncio
async def test_all_customers_ledger_summary(seeded_session):
    res = await service.get_balance(seeded_session)
    assert res["active_accounts"] >= 2  # Ramesh (500) and Priya (200)
    assert res["total_receivable"] == 700.0


@pytest.mark.asyncio
async def test_khata_tools_registry(seeded_session):
    # Test adding credit via tool registry
    res = await registry.execute(
        name="add_credit",
        session=seeded_session,
        arguments={
            "customer_name": "Suresh Patel",
            "amount": 250.0,
            "note": "Sugar & oil",
        },
    )
    assert "error" not in res
    assert res["current_balance"] == 250.0

    # Test querying balance
    bal_res = await registry.execute(
        name="get_khata_balance",
        session=seeded_session,
        arguments={"customer_name": "Suresh Patel"},
    )
    assert "error" not in bal_res
    assert bal_res["current_balance"] == 250.0

"""Unit & Integration Tests validating fixes for Issues 1, 2, and 3."""

import pytest
from app.agent.tool_registry import registry
from app.agent.agent import agent
from app.billing import service as billing_service
from app.core.errors import InsufficientStockError
import app.billing.tools
import app.documents.tools
import app.inventory.tools


@pytest.mark.asyncio
async def test_issue_1_ambiguity_no_static_fallback(seeded_session):
    """
    Issue 1 Fix Verification:
    Sending 'Add atta' must not hit a canned static template.
    It should dynamically look up the catalog, find the matching SKUs (e.g. Aashirvaad Atta & Loose Wheat Atta),
    and ask the owner to choose between them with actual product names and prices.
    """
    resp = await agent._execute_grounded_fallback(
        user_message="add atta",
        session=seeded_session,
        artifacts_collected=[],
    )
    # Ensure it is not a canned "I received: 'Add atta'" menu
    assert "I received: \"Add atta\"" not in resp.text
    assert "Try asking:" not in resp.text
    # Ensure it provides dynamic options found in the database
    assert "Aashirvaad Atta 5kg" in resp.text
    assert "Loose Wheat Atta" in resp.text
    assert "Which one" in resp.text or "select" in resp.text


@pytest.mark.asyncio
async def test_issue_2_invoice_ordering_selectors(seeded_session):
    """
    Issue 2 Fix Verification:
    Seed multiple bills, verify 'first' returns Bill #1, 'last' returns latest bill,
    and 'specific' with bill_id returns that exact bill.
    """
    # Create Bill 1
    b1 = await billing_service.start_or_update_bill(
        session=seeded_session,
        items=[{"name": "Tata Salt 1kg", "quantity": 1.0}],
    )
    await billing_service.finalize_bill(seeded_session, bill_id=b1["bill_id"])

    # Create Bill 2
    b2 = await billing_service.start_or_update_bill(
        session=seeded_session,
        items=[{"name": "Maggi 70g", "quantity": 2.0}],
    )
    await billing_service.finalize_bill(seeded_session, bill_id=b2["bill_id"])

    # Create Bill 3
    b3 = await billing_service.start_or_update_bill(
        session=seeded_session,
        items=[{"name": "Loose Sugar", "quantity": 1.0}],
    )
    await billing_service.finalize_bill(seeded_session, bill_id=b3["bill_id"])

    # Test Selector: "first"
    bill_first = await billing_service.get_bill_by_selector(seeded_session, order="first")
    assert bill_first is not None
    assert bill_first.id == b1["bill_id"]

    # Test Selector: "last"
    bill_last = await billing_service.get_bill_by_selector(seeded_session, order="last")
    assert bill_last is not None
    assert bill_last.id == b3["bill_id"]

    # Test Selector: "specific" (e.g. Bill #2)
    bill_specific = await billing_service.get_bill_by_selector(seeded_session, bill_id=b2["bill_id"], order="specific")
    assert bill_specific is not None
    assert bill_specific.id == b2["bill_id"]

    # Tool invocation test: generate_invoice_pdf with order="first"
    pdf_first_res = await registry.execute(
        name="generate_invoice_pdf",
        session=seeded_session,
        arguments={"order": "first"},
    )
    assert pdf_first_res["success"] is True
    assert pdf_first_res["bill_id"] == b1["bill_id"]

    # Tool invocation test: generate_invoice_pdf with order="last"
    pdf_last_res = await registry.execute(
        name="generate_invoice_pdf",
        session=seeded_session,
        arguments={"order": "last"},
    )
    assert pdf_last_res["success"] is True
    assert pdf_last_res["bill_id"] == b3["bill_id"]


@pytest.mark.asyncio
async def test_issue_3_draft_oversell_warning_and_finalize_hard_block(seeded_session):
    """
    Issue 3 Fix Verification:
    Adding 50 packets of Aashirvaad Atta 5kg (when only 20 packets in stock) into a draft:
    1. Should be accepted into the draft.
    2. Must return a clear warning field detailing available vs requested stock.
    3. Finalize MUST reject with InsufficientStockError to guard inventory.
    """
    # Aashirvaad Atta 5kg has initial stock of 20 packets
    preview = await billing_service.start_or_update_bill(
        session=seeded_session,
        items=[{"name": "Aashirvaad Atta 5kg", "quantity": 50.0}],
    )

    # 1. Draft accepts item
    assert preview["item_count"] == 1
    assert preview["items"][0]["quantity"] == 50.0

    # 2. Warning is present in preview
    assert preview["has_oversell_warning"] is True
    assert len(preview["warnings"]) > 0
    assert "Stock Alert" in preview["warnings"][0]
    assert "only 20.0 packet in stock" in preview["warnings"][0]

    # 3. Finalize must reject with hard block
    with pytest.raises(InsufficientStockError) as exc_info:
        await billing_service.finalize_bill(
            session=seeded_session,
            bill_id=preview["bill_id"],
        )
    assert "Aashirvaad Atta 5kg" in str(exc_info.value)


@pytest.mark.asyncio
async def test_payment_method_respected_on_complete_and_invoice(seeded_session):
    """
    Test that when user says 'Complete bill and generate invoice with cash payment',
    the bill is finalized with payment_method='CASH' and the PDF invoice specifies CASH.
    """
    # 1. Add items to bill draft
    add_resp = await agent._execute_grounded_fallback(
        user_message="add 1kg sugar and 2 maggi",
        session=seeded_session,
        artifacts_collected=[],
    )
    assert add_resp.active_bill_id is not None
    assert "Sugar" in add_resp.text

    # 2. Checkout with cash payment
    checkout_resp = await agent._execute_grounded_fallback(
        user_message="Complete bill and generate invoice with cash payment",
        session=seeded_session,
        artifacts_collected=[],
    )
    assert "CASH" in checkout_resp.text
    assert len(checkout_resp.artifacts) == 1
    assert checkout_resp.artifacts[0]["type"] == "pdf"

    # Verify bill status and payment method in DB
    bill_data = await billing_service.preview_bill(seeded_session, bill_id=add_resp.active_bill_id)
    assert bill_data["status"] == "FINALIZED"
    assert bill_data["payment_method"] == "CASH"



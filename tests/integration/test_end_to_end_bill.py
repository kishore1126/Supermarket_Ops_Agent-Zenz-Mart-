"""End-to-End Integration Test: Complete Kirana Store Lifecycle from the Brief."""

import os
from pathlib import Path
import pytest
from app.inventory import service as inv_service
from app.billing import service as bill_service
from app.khata import service as khata_service
from app.analytics import service as analytics_service
from app.preferences import service as pref_service
from app.documents.invoice_pdf import generate_invoice_pdf
from app.documents.analysis_pptx import generate_analysis_deck
from app.agent.agent import agent


@pytest.mark.asyncio
async def test_complete_kirana_lifecycle(seeded_session):
    chat_id = "test_e2e_chat"

    # Step 1: Stock query
    maggi_stock = await inv_service.check_stock(seeded_session, query="Maggi 70g")
    assert maggi_stock[0]["stock_qty"] == 150.0

    # Step 2: Receive Stock ("50 packets of Maggi came in, cost ₹12, MRP ₹14")
    rcv_res = await inv_service.receive_stock(
        session=seeded_session,
        product_name="Maggi 70g",
        quantity=50.0,
        cost_price=12.0,
        mrp=14.0,
    )
    assert rcv_res["success"] is True
    assert rcv_res["current_stock"] == 200.0

    # Step 3: Cut Draft Bill ("make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, 1 Amul butter, UPI")
    draft_items = [
        {"name": "Loose Sugar", "quantity": 2.0},
        {"name": "Aashirvaad Atta 5kg", "quantity": 1.0},
        {"name": "Maggi 70g", "quantity": 4.0},
        {"name": "Amul Butter 100g", "quantity": 1.0},
    ]
    draft_preview = await bill_service.start_or_update_bill(
        session=seeded_session,
        items=draft_items,
        payment_method="UPI",
    )
    bill_id = draft_preview["bill_id"]
    assert draft_preview["item_count"] == 4
    assert draft_preview["total"] == 447.0

    # Verify inventory was untouched
    maggi_check = await inv_service.check_stock(seeded_session, query="Maggi 70g")
    assert maggi_check[0]["stock_qty"] == 200.0

    # Step 4: Edit Draft Bill ("drop the butter, make it 6 Maggi")
    edit_items = [
        {"name": "Amul Butter 100g", "quantity": 0.0},  # drop
        {"name": "Maggi 70g", "quantity": 6.0},         # update qty
    ]
    updated_preview = await bill_service.start_or_update_bill(
        session=seeded_session,
        items=edit_items,
        bill_id=bill_id,
    )
    assert updated_preview["item_count"] == 3
    # 2kg Sugar (88) + 1 Atta (245) + 6 Maggi (84) = 417.00
    assert updated_preview["total"] == 417.0

    # Step 5: Finalize Bill (Stock decrements atomically)
    fin_res = await bill_service.finalize_bill(
        session=seeded_session,
        bill_id=bill_id,
    )
    assert fin_res["success"] is True
    assert fin_res["status"] == "FINALIZED"

    # Verify stock decremented
    maggi_after = await inv_service.check_stock(seeded_session, query="Maggi 70g")
    assert maggi_after[0]["stock_qty"] == 194.0  # 200 - 6

    # Step 6: Generate Real GST Invoice PDF
    pdf_path = generate_invoice_pdf(
        bill_data=updated_preview,
        shop_info={"shop_name": "Maa Durga Kirana Store"},
    )
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 1000

    # Step 7: Khata Cycle ("put ₹500 on Ramesh's credit" -> "Ramesh paid ₹300")
    credit_res = await khata_service.add_credit(
        session=seeded_session,
        customer_name="Ramesh Kumar",
        amount=500.0,
        note="Monthly credit addition",
    )
    assert credit_res["current_balance"] == 1000.0  # 500 opening + 500

    pay_res = await khata_service.record_payment(
        session=seeded_session,
        customer_name="Ramesh Kumar",
        amount=300.0,
        note="GPay transfer",
    )
    assert pay_res["current_balance"] == 700.0

    # Step 8: Daily Close & Weekly PPTX Deck
    close_data = await analytics_service.get_daily_close(seeded_session)
    assert close_data["total_bills"] >= 1
    assert close_data["total_sales"] >= 417.0

    sales_data = await analytics_service.get_sales_analysis(seeded_session, days=7)
    pptx_path = generate_analysis_deck(
        sales_data=sales_data,
        low_stock_items=[],
    )
    assert os.path.exists(pptx_path)
    assert os.path.getsize(pptx_path) > 5000

    # Step 9: Preferences & Memory across /new
    await pref_service.set_preference(
        session=seeded_session,
        key="default_payment_method",
        value="Cash",
    )
    # Reset conversation memory (simulating /new command)
    agent.reset_conversation(chat_id)

    # Verify preference is still remembered from database!
    current_default_pay = await pref_service.get_preference(
        session=seeded_session,
        key="default_payment_method",
    )
    assert current_default_pay == "Cash"

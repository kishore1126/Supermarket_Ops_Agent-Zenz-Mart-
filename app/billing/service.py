"""Billing Service: Draft state machine, tax aggregation, and atomic finalize with row locking."""

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models import Bill, BillItem, BillStatus
from app.billing.gst import calculate_invoice_gst
from app.inventory.models import Product
from app.inventory.service import get_product_by_name
from app.khata.models import Customer, KhataEntry, KhataType
from app.core.errors import (
    BillAlreadyFinalizedError,
    BillCancelledError,
    BillNotFoundError,
    EmptyBillError,
    InsufficientStockError,
    ProductNotFoundError,
    InvalidOperationError,
)
from app.core.transactions import record_audit_log


async def get_bill_by_id(session: AsyncSession, bill_id: int) -> Bill | None:
    """Get bill by primary key ID with loaded items."""
    stmt = (
        select(Bill)
        .options(selectinload(Bill.items), selectinload(Bill.customer))
        .where(Bill.id == bill_id)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_latest_draft_bill(session: AsyncSession) -> Bill | None:
    """Retrieve the most recent open draft bill with loaded items."""
    stmt = (
        select(Bill)
        .options(selectinload(Bill.items), selectinload(Bill.customer))
        .where(Bill.status == BillStatus.DRAFT)
        .order_by(Bill.created_at.desc())
        .limit(1)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


def _recalculate_bill_totals(bill: Bill) -> None:
    """Recompute all item tax breakdowns and invoice totals from draft items."""
    if not bill.items:
        bill.subtotal = 0.0
        bill.cgst = 0.0
        bill.sgst = 0.0
        bill.round_off = 0.0
        bill.total = 0.0
        return

    items_data = [
        {
            "name": item.product_name,
            "unit": item.unit,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "gst_rate": item.gst_rate,
            "hsn_code": item.hsn_code,
        }
        for item in bill.items
    ]

    gst_summary = calculate_invoice_gst(items_data)

    # Update item level amounts
    for item, calculated in zip(bill.items, gst_summary.items):
        item.taxable_value = calculated.taxable_value
        item.cgst_amount = calculated.cgst_amount
        item.sgst_amount = calculated.sgst_amount
        item.tax_amount = calculated.tax_amount
        item.line_total = calculated.line_total

    # Update invoice level amounts
    bill.subtotal = gst_summary.subtotal
    bill.cgst = gst_summary.total_cgst
    bill.sgst = gst_summary.total_sgst
    bill.round_off = gst_summary.round_off
    bill.total = gst_summary.final_total


async def start_or_update_bill(
    session: AsyncSession,
    items: list[dict],
    customer_name: str | None = None,
    customer_phone: str | None = None,
    payment_method: str | None = None,
    bill_id: int | None = None,
) -> dict:
    """
    Start a new draft bill or update an existing open draft.
    
    Items list can add items, update quantities, or remove items (if qty <= 0).
    Does NOT decrement inventory stock (stock is only decremented on finalize_bill).
    """
    if bill_id:
        bill = await get_bill_by_id(session, bill_id)
        if not bill:
            raise BillNotFoundError(bill_id)
        if bill.status == BillStatus.FINALIZED:
            raise BillAlreadyFinalizedError(bill_id)
        if bill.status == BillStatus.CANCELLED:
            raise BillCancelledError(bill_id)
    else:
        bill = await get_latest_draft_bill(session)
        if not bill:
            bill = Bill(status=BillStatus.DRAFT, items=[])
            session.add(bill)
            await session.flush()

    # Update customer / payment if provided
    if customer_name is not None:
        bill.customer_name = customer_name.strip()
        # Associate customer record if exists
        c_stmt = select(Customer).where(Customer.name.ilike(bill.customer_name))
        c_res = await session.execute(c_stmt)
        c = c_res.scalar_one_or_none()
        if c:
            bill.customer_id = c.id
    if customer_phone is not None:
        bill.customer_phone = customer_phone.strip()
    if payment_method is not None:
        bill.payment_method = payment_method.strip().upper()

    # Map existing items by product_id
    existing_items_map = {item.product_id: item for item in bill.items}

    # Process items
    for item_input in items:
        p_name = item_input.get("product_name") or item_input.get("name")
        p_id = item_input.get("product_id")
        qty = float(item_input.get("quantity", 1.0))

        # Lookup product
        if p_id:
            stmt = select(Product).where(Product.id == p_id)
            res = await session.execute(stmt)
            product = res.scalar_one_or_none()
        else:
            product = await get_product_by_name(session, p_name)

        if not product:
            raise ProductNotFoundError(p_name or f"ID #{p_id}")

        # Check if item exists in bill
        existing_item = existing_items_map.get(product.id)

        if qty <= 0:
            # Drop item
            if existing_item:
                bill.items.remove(existing_item)
        else:
            # Ground price from DB unless explicitly specified
            unit_price = float(item_input.get("unit_price") or product.selling_price)
            if existing_item:
                # Update existing
                existing_item.quantity = qty
                existing_item.unit_price = unit_price
            else:
                # Add new item
                new_item = BillItem(
                    bill_id=bill.id,
                    product_id=product.id,
                    product_name=product.name,
                    unit=product.unit,
                    quantity=qty,
                    unit_price=unit_price,
                    gst_rate=product.gst_rate,
                    hsn_code=product.hsn_code,
                )
                bill.items.append(new_item)

    _recalculate_bill_totals(bill)
    await session.flush()

    return await preview_bill(session, bill_id=bill.id)


async def preview_bill(
    session: AsyncSession,
    bill_id: int | None = None,
) -> dict:
    """Generate structured preview of the current or specified draft bill."""
    if bill_id:
        bill = await get_bill_by_id(session, bill_id)
    else:
        bill = await get_latest_draft_bill(session)

    if not bill:
        return {"status": "NO_ACTIVE_DRAFT", "message": "No active draft bill found."}

    _recalculate_bill_totals(bill)

    items_list = [
        {
            "id": item.id,
            "product_id": item.product_id,
            "product_name": item.product_name,
            "unit": item.unit,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "gst_rate": item.gst_rate,
            "gst_rate_pct": f"{int(item.gst_rate * 100)}%",
            "hsn_code": item.hsn_code,
            "taxable_value": item.taxable_value,
            "tax_amount": item.tax_amount,
            "line_total": item.line_total,
        }
        for item in bill.items
    ]

    return {
        "bill_id": bill.id,
        "status": bill.status.value,
        "customer_name": bill.customer_name or "Walk-in Customer",
        "customer_phone": bill.customer_phone,
        "payment_method": bill.payment_method,
        "items": items_list,
        "item_count": len(items_list),
        "subtotal": bill.subtotal,
        "cgst": bill.cgst,
        "sgst": bill.sgst,
        "total_tax": round(bill.cgst + bill.sgst, 2),
        "round_off": bill.round_off,
        "total": bill.total,
        "created_at": bill.created_at.isoformat(),
    }


async def finalize_bill(
    session: AsyncSession,
    bill_id: int | None = None,
    payment_method: str | None = None,
    allow_below_cost: bool = False,
) -> dict:
    """
    Finalize a draft bill atomically with PostgreSQL row-level locks on inventory products.
    
    1. Checks bill is in DRAFT status.
    2. Locks product rows using SELECT ... FOR UPDATE.
    3. Verifies stock availability for every item; raises InsufficientStockError if violated.
    4. Decrements stock_qty atomically.
    5. Transitions bill status to FINALIZED.
    6. If Khata payment, logs ledger credit.
    7. Writes audit log.
    """
    if bill_id:
        bill = await get_bill_by_id(session, bill_id)
    else:
        bill = await get_latest_draft_bill(session)

    if not bill:
        raise BillNotFoundError(bill_id or 0)
    if bill.status == BillStatus.FINALIZED:
        raise BillAlreadyFinalizedError(bill.id)
    if bill.status == BillStatus.CANCELLED:
        raise BillCancelledError(bill.id)
    if not bill.items:
        raise EmptyBillError(bill.id)

    if payment_method:
        bill.payment_method = payment_method.strip().upper()

    # Extract unique product IDs
    product_ids = list({item.product_id for item in bill.items})

    # Execute row-level lock on involved products
    # Note: with_for_update() applies SELECT ... FOR UPDATE on Postgres
    lock_stmt = select(Product).where(Product.id.in_(product_ids)).with_for_update()
    locked_res = await session.execute(lock_stmt)
    locked_products = {p.id: p for p in locked_res.scalars().all()}

    # Check oversell guard for every line item
    for item in bill.items:
        product = locked_products.get(item.product_id)
        if not product:
            raise ProductNotFoundError(f"ID #{item.product_id}")

        if product.stock_qty < item.quantity:
            raise InsufficientStockError(
                product_name=product.name,
                requested=item.quantity,
                available=product.stock_qty,
            )

    # Decrement stock atomically
    for item in bill.items:
        product = locked_products[item.product_id]
        product.stock_qty -= item.quantity

    # Finalize bill
    _recalculate_bill_totals(bill)
    bill.status = BillStatus.FINALIZED
    bill.finalized_at = datetime.now(timezone.utc)

    # Handle Khata payment if applicable
    if bill.payment_method.upper() == "KHATA":
        cust_name = bill.customer_name or "Walk-in Customer"
        c_stmt = select(Customer).where(Customer.name.ilike(cust_name))
        c_res = await session.execute(c_stmt)
        customer = c_res.scalar_one_or_none()
        if not customer:
            customer = Customer(name=cust_name, phone=bill.customer_phone)
            session.add(customer)
            await session.flush()
        bill.customer_id = customer.id

        khata_entry = KhataEntry(
            customer_id=customer.id,
            type=KhataType.CREDIT,
            amount=bill.total,
            bill_id=bill.id,
            note=f"Bill #{bill.id} purchase",
        )
        session.add(khata_entry)

    # Record Audit Log
    await record_audit_log(
        session,
        action_type="BILL_FINALIZED",
        reference_id=f"bill_{bill.id}",
        payload={
            "bill_id": bill.id,
            "total": bill.total,
            "payment_method": bill.payment_method,
            "item_count": len(bill.items),
            "customer": bill.customer_name,
        },
    )

    await session.flush()

    return {
        "success": True,
        "bill_id": bill.id,
        "status": bill.status.value,
        "total": bill.total,
        "payment_method": bill.payment_method,
        "customer_name": bill.customer_name or "Walk-in Customer",
        "item_count": len(bill.items),
        "finalized_at": bill.finalized_at.isoformat() if bill.finalized_at else None,
        "message": f"Bill #{bill.id} finalized successfully for ₹{bill.total:.2f} via {bill.payment_method}."
    }


async def cancel_bill(
    session: AsyncSession,
    bill_id: int | None = None,
) -> dict:
    """Cancel a draft bill."""
    if bill_id:
        bill = await get_bill_by_id(session, bill_id)
    else:
        bill = await get_latest_draft_bill(session)

    if not bill:
        raise BillNotFoundError(bill_id or 0)
    if bill.status == BillStatus.FINALIZED:
        raise BillAlreadyFinalizedError(bill.id)

    bill.status = BillStatus.CANCELLED
    await session.flush()

    return {
        "success": True,
        "bill_id": bill.id,
        "status": bill.status.value,
        "message": f"Bill #{bill.id} has been cancelled."
    }

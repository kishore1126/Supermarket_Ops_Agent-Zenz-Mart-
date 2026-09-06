"""Khata (Customer Ledger) Service: Credit tracking, payment settlements, and balance calculations."""

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.khata.models import Customer, KhataEntry, KhataType
from app.core.errors import CustomerNotFoundError, InvalidOperationError
from app.core.transactions import record_audit_log


async def get_customer_by_name(session: AsyncSession, name: str) -> Customer | None:
    """Find customer by case-insensitive name match."""
    clean_name = name.strip()
    stmt = (
        select(Customer)
        .options(selectinload(Customer.khata_entries))
        .where(Customer.name.ilike(clean_name))
    )
    res = await session.execute(stmt)
    cust = res.scalar_one_or_none()
    if cust:
        return cust
    
    # Substring search if exact match fails
    stmt_sub = (
        select(Customer)
        .options(selectinload(Customer.khata_entries))
        .where(Customer.name.ilike(f"%{clean_name}%"))
        .limit(1)
    )
    res_sub = await session.execute(stmt_sub)
    return res_sub.scalar_one_or_none()


def calculate_customer_balance(customer: Customer) -> float:
    """Calculate current outstanding balance owed by customer (Credits - Payments)."""
    total_credit = sum(e.amount for e in customer.khata_entries if e.type == KhataType.CREDIT)
    total_payment = sum(e.amount for e in customer.khata_entries if e.type == KhataType.PAYMENT)
    return round(total_credit - total_payment, 2)


async def add_credit(
    session: AsyncSession,
    customer_name: str,
    amount: float,
    note: str | None = None,
    phone: str | None = None,
) -> dict:
    """Add credit to a customer's ledger account."""
    if amount <= 0:
        raise InvalidOperationError("Credit amount must be greater than 0.")

    customer = await get_customer_by_name(session, customer_name)
    if not customer:
        customer = Customer(
            name=customer_name.strip(),
            phone=phone.strip() if phone else None,
            khata_entries=[],
        )
        session.add(customer)
        await session.flush()

    entry = KhataEntry(
        customer_id=customer.id,
        type=KhataType.CREDIT,
        amount=amount,
        note=note or "Manual credit entry",
    )
    session.add(entry)
    customer.khata_entries.append(entry)
    await session.flush()

    new_balance = calculate_customer_balance(customer)

    await record_audit_log(
        session,
        action_type="KHATA_CREDIT",
        reference_id=f"customer_{customer.id}",
        payload={"customer": customer.name, "credit_added": amount, "new_balance": new_balance},
    )

    return {
        "success": True,
        "customer_id": customer.id,
        "customer_name": customer.name,
        "credit_added": amount,
        "current_balance": new_balance,
        "message": f"Added ₹{amount:.2f} credit to {customer.name}'s khata. Total balance owed: ₹{new_balance:.2f}."
    }


async def record_payment(
    session: AsyncSession,
    customer_name: str,
    amount: float,
    note: str | None = None,
) -> dict:
    """Record a cash/UPI payment made by customer to clear khata balance."""
    if amount <= 0:
        raise InvalidOperationError("Payment amount must be greater than 0.")

    customer = await get_customer_by_name(session, customer_name)
    if not customer:
        raise CustomerNotFoundError(customer_name)

    old_balance = calculate_customer_balance(customer)

    entry = KhataEntry(
        customer_id=customer.id,
        type=KhataType.PAYMENT,
        amount=amount,
        note=note or "Customer payment / settlement",
    )
    session.add(entry)
    customer.khata_entries.append(entry)
    await session.flush()

    new_balance = calculate_customer_balance(customer)

    await record_audit_log(
        session,
        action_type="KHATA_PAYMENT",
        reference_id=f"customer_{customer.id}",
        payload={"customer": customer.name, "payment": amount, "old_balance": old_balance, "new_balance": new_balance},
    )

    status_msg = "fully cleared" if new_balance == 0 else f"remaining balance is ₹{new_balance:.2f}"
    return {
        "success": True,
        "customer_id": customer.id,
        "customer_name": customer.name,
        "payment_recorded": amount,
        "previous_balance": old_balance,
        "current_balance": new_balance,
        "is_cleared": new_balance <= 0,
        "message": f"Recorded payment of ₹{amount:.2f} from {customer.name}. Account is {status_msg}."
    }


async def get_balance(
    session: AsyncSession,
    customer_name: str | None = None,
) -> dict:
    """Get customer balance or list all open customer credit accounts in store."""
    if customer_name and customer_name.strip():
        customer = await get_customer_by_name(session, customer_name)
        if not customer:
            raise CustomerNotFoundError(customer_name)

        balance = calculate_customer_balance(customer)
        entries = [
            {
                "id": e.id,
                "type": e.type.value,
                "amount": e.amount,
                "note": e.note,
                "date": e.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for e in sorted(customer.khata_entries, key=lambda x: x.created_at, reverse=True)[:10]
        ]
        return {
            "customer_id": customer.id,
            "customer_name": customer.name,
            "phone": customer.phone,
            "current_balance": balance,
            "recent_entries": entries,
            "message": f"{customer.name}'s current khata balance: ₹{balance:.2f}."
        }

    # All customers summary
    stmt = select(Customer).options(selectinload(Customer.khata_entries)).order_by(Customer.name)
    res = await session.execute(stmt)
    all_customers = res.scalars().all()

    ledger = []
    total_receivable = 0.0

    for c in all_customers:
        bal = calculate_customer_balance(c)
        if bal != 0.0:
            ledger.append({
                "customer_id": c.id,
                "customer_name": c.name,
                "phone": c.phone,
                "balance": bal,
            })
            if bal > 0:
                total_receivable += bal

    return {
        "active_accounts": len(ledger),
        "total_receivable": round(total_receivable, 2),
        "customers": ledger,
        "message": f"Total outstanding khata receivable: ₹{total_receivable:.2f} across {len(ledger)} customers."
    }

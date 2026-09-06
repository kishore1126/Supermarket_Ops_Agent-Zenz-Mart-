"""Khata Tools exposed to the Agent."""

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tool_registry import registry
from app.khata import service


class AddCreditInput(BaseModel):
    customer_name: str = Field(..., description="Name of the customer (e.g. 'Ramesh', 'Suresh Patel').")
    amount: float = Field(..., description="Amount in ₹ added to credit / debt.")
    note: str | None = Field(None, description="Optional note (e.g. 'Monthly ration', 'Oil & sugar').")
    phone: str | None = Field(None, description="Optional customer phone number.")


class RecordPaymentInput(BaseModel):
    customer_name: str = Field(..., description="Name of the customer paying money back (e.g. 'Ramesh').")
    amount: float = Field(..., description="Amount in ₹ paid back by customer.")
    note: str | None = Field(None, description="Optional payment note (e.g. 'GPay', 'Cash handed over').")


class GetKhataBalanceInput(BaseModel):
    customer_name: str | None = Field(
        None,
        description="Optional customer name. If empty, returns summary of all outstanding khata balances.",
    )


@registry.register(
    name="add_credit",
    description="Add credit / debt to a customer's khata ledger when they buy goods on credit.",
    schema=AddCreditInput,
)
async def add_credit_tool(
    session: AsyncSession,
    customer_name: str,
    amount: float,
    note: str | None = None,
    phone: str | None = None,
    **kwargs,
) -> dict:
    try:
        res = await service.add_credit(
            session=session,
            customer_name=customer_name,
            amount=amount,
            note=note,
            phone=phone,
        )
        await session.commit()
        return res
    except Exception as e:
        await session.rollback()
        return {"error": str(e)}


@registry.register(
    name="record_payment",
    description="Record a cash or UPI payment from a customer settling their khata balance.",
    schema=RecordPaymentInput,
)
async def record_payment_tool(
    session: AsyncSession,
    customer_name: str,
    amount: float,
    note: str | None = None,
    **kwargs,
) -> dict:
    try:
        res = await service.record_payment(
            session=session,
            customer_name=customer_name,
            amount=amount,
            note=note,
        )
        await session.commit()
        return res
    except Exception as e:
        await session.rollback()
        return {"error": str(e)}


@registry.register(
    name="get_khata_balance",
    description="Query a specific customer's khata ledger balance or get total store credit receivables.",
    schema=GetKhataBalanceInput,
)
async def get_khata_balance_tool(
    session: AsyncSession,
    customer_name: str | None = None,
    **kwargs,
) -> dict:
    try:
        res = await service.get_balance(session, customer_name=customer_name)
        return res
    except Exception as e:
        return {"error": str(e)}

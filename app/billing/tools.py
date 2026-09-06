"""Billing Tools exposed to the Agent."""

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tool_registry import registry
from app.billing import service


class BillItemInput(BaseModel):
    product_name: str | None = Field(None, description="Name of the product (e.g. 'sugar', 'Maggi 70g', 'Tata Salt').")
    product_id: int | None = Field(None, description="Product database ID if known.")
    quantity: float = Field(..., description="Quantity to buy. Set to 0 or negative to remove/drop item from draft bill.")
    unit_price: float | None = Field(None, description="Optional selling price override in ₹. Defaults to DB price.")


class StartOrUpdateBillInput(BaseModel):
    items: list[BillItemInput] = Field(..., description="List of items to add, modify quantity of, or drop from the bill.")
    customer_name: str | None = Field(None, description="Customer name if known or provided.")
    customer_phone: str | None = Field(None, description="Customer phone number if provided.")
    payment_method: str | None = Field(None, description="Payment mode: 'UPI', 'Cash', 'Card', or 'Khata'.")
    bill_id: int | None = Field(None, description="Existing draft bill ID to modify, or None for current/new draft.")


class PreviewBillInput(BaseModel):
    bill_id: int | None = Field(None, description="Bill ID to preview, or None for current open draft.")


class FinalizeBillInput(BaseModel):
    bill_id: int | None = Field(None, description="Bill ID to finalize, or None for current open draft.")
    payment_method: str | None = Field(None, description="Final payment method ('UPI', 'Cash', 'Card', 'Khata').")
    allow_below_cost: bool = Field(False, description="Set True if owner confirmed selling below cost.")


class CancelBillInput(BaseModel):
    bill_id: int | None = Field(None, description="Bill ID to cancel, or None for current open draft.")


@registry.register(
    name="start_or_update_bill",
    description="Start a new draft bill or add/modify/remove items on the current open draft bill.",
    schema=StartOrUpdateBillInput,
)
async def start_or_update_bill_tool(
    session: AsyncSession,
    items: list[dict | BillItemInput],
    customer_name: str | None = None,
    customer_phone: str | None = None,
    payment_method: str | None = None,
    bill_id: int | None = None,
    **kwargs,
) -> dict:
    try:
        items_raw = [i.model_dump() if isinstance(i, BaseModel) else i for i in items]
        res = await service.start_or_update_bill(
            session=session,
            items=items_raw,
            customer_name=customer_name,
            customer_phone=customer_phone,
            payment_method=payment_method,
            bill_id=bill_id,
        )
        await session.commit()
        return res
    except Exception as e:
        await session.rollback()
        return {"error": str(e)}


@registry.register(
    name="preview_bill",
    description="Preview the current draft bill breakdown (items, GST breakup, round-off, total) before confirmation.",
    schema=PreviewBillInput,
)
async def preview_bill_tool(
    session: AsyncSession,
    bill_id: int | None = None,
    **kwargs,
) -> dict:
    try:
        res = await service.preview_bill(session, bill_id=bill_id)
        return res
    except Exception as e:
        return {"error": str(e)}


@registry.register(
    name="finalize_bill",
    description="Finalize the bill, decrementing inventory stock atomically with row locks and generating final total.",
    schema=FinalizeBillInput,
)
async def finalize_bill_tool(
    session: AsyncSession,
    bill_id: int | None = None,
    payment_method: str | None = None,
    allow_below_cost: bool = False,
    **kwargs,
) -> dict:
    try:
        res = await service.finalize_bill(
            session=session,
            bill_id=bill_id,
            payment_method=payment_method,
            allow_below_cost=allow_below_cost,
        )
        await session.commit()
        return res
    except Exception as e:
        await session.rollback()
        return {"error": str(e)}


@registry.register(
    name="cancel_bill",
    description="Cancel an active draft bill without modifying inventory stock.",
    schema=CancelBillInput,
)
async def cancel_bill_tool(
    session: AsyncSession,
    bill_id: int | None = None,
    **kwargs,
) -> dict:
    try:
        res = await service.cancel_bill(session, bill_id=bill_id)
        await session.commit()
        return res
    except Exception as e:
        await session.rollback()
        return {"error": str(e)}

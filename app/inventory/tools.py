"""Inventory Tools exposed to the Agent."""

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tool_registry import registry
from app.inventory import service


class CheckStockInput(BaseModel):
    query: str | None = Field(
        None,
        description="Product name or keyword to search in inventory (e.g., 'sugar', 'Maggi', 'atta').",
    )
    product_id: int | None = Field(
        None,
        description="Optional exact product ID.",
    )


class GetLowStockInput(BaseModel):
    pass


class ReceiveStockInput(BaseModel):
    product_name: str = Field(..., description="Name of the product being received (e.g. 'Maggi 70g').")
    quantity: float = Field(..., description="Quantity received in product units (packets, kg, pouches, etc.).")
    cost_price: float | None = Field(None, description="Optional updated purchase cost price in ₹ per unit.")
    mrp: float | None = Field(None, description="Optional updated Maximum Retail Price in ₹ per unit.")
    selling_price: float | None = Field(None, description="Optional updated selling price in ₹ per unit.")
    allow_below_cost: bool = Field(False, description="Set to True if owner explicitly confirmed selling below cost.")


class AddProductInput(BaseModel):
    name: str = Field(..., description="Full name of the new product SKU (e.g. 'Amul Butter 100g').")
    unit: str = Field("packet", description="Measurement unit: kg, g, litre, ml, packet, piece, dozen, pouch.")
    cost_price: float = Field(..., description="Wholesale purchase cost price per unit in ₹.")
    selling_price: float = Field(..., description="Store selling price per unit in ₹.")
    mrp: float = Field(..., description="Maximum Retail Price printed on pack in ₹.")
    gst_rate: float = Field(0.0, description="GST slab rate as decimal: 0.0 (0%), 0.05 (5%), 0.12 (12%), 0.18 (18%), 0.28 (28%).")
    hsn_code: str = Field("0000", description="Harmonized System of Nomenclature (HSN) code for GST reporting.")
    initial_stock: float = Field(0.0, description="Initial stock quantity available on shelves.")
    reorder_level: float = Field(5.0, description="Threshold quantity below which low-stock warning triggers.")
    allow_below_cost: bool = Field(False, description="Set to True if owner explicitly confirmed selling below cost.")


@registry.register(
    name="check_stock",
    description="Check current stock levels, prices, and GST rates for products in the store.",
    schema=CheckStockInput,
)
async def check_stock_tool(
    session: AsyncSession,
    query: str | None = None,
    product_id: int | None = None,
    **kwargs,
) -> dict:
    try:
        results = await service.check_stock(session, query=query, product_id=product_id)
        return {"count": len(results), "products": results}
    except Exception as e:
        return {"error": str(e)}


@registry.register(
    name="get_low_stock",
    description="Get list of items that are currently running low or below their reorder threshold.",
    schema=GetLowStockInput,
)
async def get_low_stock_tool(
    session: AsyncSession,
    **kwargs,
) -> dict:
    try:
        results = await service.get_low_stock(session)
        return {"count": len(results), "low_stock_items": results}
    except Exception as e:
        return {"error": str(e)}


@registry.register(
    name="receive_stock",
    description="Record newly received inventory / stock delivery for an existing product.",
    schema=ReceiveStockInput,
)
async def receive_stock_tool(
    session: AsyncSession,
    product_name: str,
    quantity: float,
    cost_price: float | None = None,
    mrp: float | None = None,
    selling_price: float | None = None,
    allow_below_cost: bool = False,
    **kwargs,
) -> dict:
    try:
        res = await service.receive_stock(
            session=session,
            product_name=product_name,
            quantity=quantity,
            cost_price=cost_price,
            mrp=mrp,
            selling_price=selling_price,
            allow_below_cost=allow_below_cost,
        )
        await session.commit()
        return res
    except Exception as e:
        await session.rollback()
        return {"error": str(e)}


@registry.register(
    name="add_product",
    description="Add a completely new SKU / product to the supermarket catalog with pricing and GST details.",
    schema=AddProductInput,
)
async def add_product_tool(
    session: AsyncSession,
    name: str,
    unit: str,
    cost_price: float,
    selling_price: float,
    mrp: float,
    gst_rate: float = 0.0,
    hsn_code: str = "0000",
    initial_stock: float = 0.0,
    reorder_level: float = 5.0,
    allow_below_cost: bool = False,
    **kwargs,
) -> dict:
    try:
        res = await service.add_product(
            session=session,
            name=name,
            unit=unit,
            cost_price=cost_price,
            selling_price=selling_price,
            mrp=mrp,
            gst_rate=gst_rate,
            hsn_code=hsn_code,
            initial_stock=initial_stock,
            reorder_level=reorder_level,
            allow_below_cost=allow_below_cost,
        )
        await session.commit()
        return res
    except Exception as e:
        await session.rollback()
        return {"error": str(e)}

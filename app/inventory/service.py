"""Inventory Business Logic Service."""

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.inventory.models import Product
from app.core.errors import (
    BelowCostError,
    ProductNotFoundError,
    InvalidOperationError,
)
from app.core.transactions import record_audit_log


async def search_products(
    session: AsyncSession,
    query: str | None = None,
    limit: int = 15,
) -> list[Product]:
    """Search active products by name with case-insensitive partial match."""
    stmt = select(Product).where(Product.is_active == True)  # noqa: E712
    if query and query.strip():
        search_pattern = f"%{query.strip().lower()}%"
        stmt = stmt.where(Product.name.ilike(search_pattern))
    stmt = stmt.order_by(Product.name).limit(limit)
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_product_by_id(session: AsyncSession, product_id: int) -> Product | None:
    """Retrieve a single product by primary key ID."""
    stmt = select(Product).where(Product.id == product_id, Product.is_active == True)  # noqa: E712
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_product_by_name(session: AsyncSession, name: str) -> Product | None:
    """Find exact or closest product match by name."""
    clean_name = name.strip()
    # Exact match first
    stmt = select(Product).where(Product.name.ilike(clean_name), Product.is_active == True)  # noqa: E712
    res = await session.execute(stmt)
    prod = res.scalar_one_or_none()
    if prod:
        return prod
    
    # Substring match
    matches = await search_products(session, clean_name, limit=5)
    if matches:
        return matches[0]
    return None


async def check_stock(
    session: AsyncSession,
    query: str | None = None,
    product_id: int | None = None,
) -> list[dict]:
    """Check stock level for specific product or search term."""
    if product_id:
        prod = await get_product_by_id(session, product_id)
        if not prod:
            raise ProductNotFoundError(f"ID #{product_id}")
        products = [prod]
    elif query and query.strip():
        products = await search_products(session, query.strip())
        if not products:
            raise ProductNotFoundError(query)
    else:
        products = await search_products(session, query=None, limit=20)

    return [
        {
            "id": p.id,
            "name": p.name,
            "unit": p.unit,
            "stock_qty": p.stock_qty,
            "selling_price": p.selling_price,
            "cost_price": p.cost_price,
            "mrp": p.mrp,
            "gst_rate": p.gst_rate,
            "hsn_code": p.hsn_code,
            "reorder_level": p.reorder_level,
            "is_low_stock": p.stock_qty <= p.reorder_level,
        }
        for p in products
    ]


async def get_low_stock(session: AsyncSession) -> list[dict]:
    """Retrieve all products where stock is at or below reorder level."""
    stmt = (
        select(Product)
        .where(Product.is_active == True, Product.stock_qty <= Product.reorder_level)  # noqa: E712
        .order_by(Product.stock_qty.asc())
    )
    res = await session.execute(stmt)
    products = res.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "unit": p.unit,
            "stock_qty": p.stock_qty,
            "reorder_level": p.reorder_level,
            "deficit": max(0.0, p.reorder_level - p.stock_qty),
            "selling_price": p.selling_price,
            "cost_price": p.cost_price,
        }
        for p in products
    ]


async def add_product(
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
) -> dict:
    """Add a new product with below-cost and non-negative guardrails."""
    if cost_price < 0 or selling_price < 0 or mrp < 0 or initial_stock < 0:
        raise InvalidOperationError("Prices and stock quantity cannot be negative.")

    # Guardrail: Selling below cost requires explicit confirmation
    if selling_price < cost_price and not allow_below_cost:
        raise BelowCostError(name, cost_price=cost_price, selling_price=selling_price)

    # Check if duplicate name exists
    existing = await get_product_by_name(session, name)
    if existing and existing.name.lower() == name.strip().lower():
        raise InvalidOperationError(f"Product '{name}' already exists. Use 'receive_stock' to update inventory.")

    product = Product(
        name=name.strip(),
        unit=unit.strip().lower(),
        cost_price=cost_price,
        selling_price=selling_price,
        mrp=mrp,
        gst_rate=gst_rate,
        hsn_code=hsn_code.strip(),
        stock_qty=initial_stock,
        reorder_level=reorder_level,
    )
    session.add(product)
    await session.flush()

    await record_audit_log(
        session,
        action_type="PRODUCT_ADD",
        reference_id=f"product_{product.id}",
        payload={
            "name": product.name,
            "unit": product.unit,
            "cost_price": product.cost_price,
            "selling_price": product.selling_price,
            "mrp": product.mrp,
            "gst_rate": product.gst_rate,
            "stock_qty": product.stock_qty,
        },
    )

    return {
        "success": True,
        "product_id": product.id,
        "name": product.name,
        "unit": product.unit,
        "stock_qty": product.stock_qty,
        "selling_price": product.selling_price,
        "cost_price": product.cost_price,
        "mrp": product.mrp,
        "gst_rate": product.gst_rate,
        "message": f"Successfully added '{product.name}' with initial stock of {product.stock_qty} {product.unit}."
    }


async def receive_stock(
    session: AsyncSession,
    product_name: str,
    quantity: float,
    cost_price: float | None = None,
    mrp: float | None = None,
    selling_price: float | None = None,
    allow_below_cost: bool = False,
) -> dict:
    """Receive incoming stock for an existing product with guardrails."""
    if quantity <= 0:
        raise InvalidOperationError("Received quantity must be greater than 0.")

    product = await get_product_by_name(session, product_name)
    if not product:
        raise ProductNotFoundError(product_name)

    old_stock = product.stock_qty
    new_stock = old_stock + quantity

    # Price updates if provided
    new_cost = cost_price if cost_price is not None else product.cost_price
    new_mrp = mrp if mrp is not None else product.mrp
    new_selling = selling_price if selling_price is not None else product.selling_price

    # Guardrail: Selling price vs cost price
    if new_selling < new_cost and not allow_below_cost:
        raise BelowCostError(product.name, cost_price=new_cost, selling_price=new_selling)

    product.stock_qty = new_stock
    product.cost_price = new_cost
    product.mrp = new_mrp
    product.selling_price = new_selling

    await record_audit_log(
        session,
        action_type="STOCK_INTAKE",
        reference_id=f"product_{product.id}",
        payload={
            "product_name": product.name,
            "added_qty": quantity,
            "old_stock": old_stock,
            "new_stock": new_stock,
            "cost_price": product.cost_price,
            "mrp": product.mrp,
            "selling_price": product.selling_price,
        },
    )

    return {
        "success": True,
        "product_id": product.id,
        "name": product.name,
        "added_quantity": quantity,
        "previous_stock": old_stock,
        "current_stock": new_stock,
        "unit": product.unit,
        "cost_price": product.cost_price,
        "selling_price": product.selling_price,
        "mrp": product.mrp,
        "message": f"Received {quantity} {product.unit} of '{product.name}'. New stock: {new_stock} {product.unit}."
    }

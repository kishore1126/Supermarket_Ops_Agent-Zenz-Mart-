"""Concurrency Race-Condition Simulation Test.

Verifies that two simultaneous finalize_bill requests racing on limited stock
serialize safely via row-level locking (SELECT ... FOR UPDATE), preventing overselling.
"""

import asyncio
import os
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from app.core.db import Base
from app.inventory.models import Product
from app.billing.models import Bill, BillItem, BillStatus
from app.billing import service as bill_service
from app.core.errors import InsufficientStockError


@pytest.mark.asyncio
async def test_concurrent_finalize_race_condition(test_engine):
    """
    Scenario:
      - Product 'Limited Biscuit' has only 5 units in stock.
      - Coroutine A tries to finalize Bill A for 4 units.
      - Coroutine B simultaneously tries to finalize Bill B for 4 units.
      - Total demand: 8 units > 5 available.
      - In PostgreSQL: SELECT ... FOR UPDATE locks the product row, serializing finalization.
        Exactly ONE transaction succeeds, and the other fails with InsufficientStockError.
    """
    # SQLite does not support true row-level locks (SELECT ... FOR UPDATE is a no-op in SQLite).
    # Check if a PostgreSQL test database is configured.
    pg_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    engine = test_engine
    is_postgres = "postgres" in (pg_url or "") or test_engine.dialect.name == "postgresql"

    if is_postgres and pg_url and "postgres" in pg_url:
        try:
            pg_engine = create_async_engine(pg_url, echo=False)
            async with pg_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            engine = pg_engine
        except Exception as e:
            pytest.skip(f"PostgreSQL test database not reachable ({e}). SQLite does not support MVCC row locks.")
    elif test_engine.dialect.name == "sqlite":
        pytest.skip(
            "Skipping concurrency race-condition test on SQLite. "
            "SQLite does not implement MVCC row-level locking (SELECT ... FOR UPDATE). "
            "Run against PostgreSQL via docker-compose (DATABASE_URL) for full MVCC verification."
        )

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    # 1. Setup initial stock & two draft bills in a setup transaction
    async with session_factory() as session:
        product = Product(
            name="Limited Biscuit",
            unit="packet",
            cost_price=20.0,
            selling_price=30.0,
            mrp=30.0,
            stock_qty=5.0,  # Only 5 in stock
            reorder_level=2.0,
        )
        session.add(product)
        await session.flush()

        # Bill 1
        bill1 = Bill(status=BillStatus.DRAFT, items=[])
        session.add(bill1)
        await session.flush()
        item1 = BillItem(
            bill_id=bill1.id,
            product_id=product.id,
            product_name=product.name,
            quantity=4.0,
            unit_price=30.0,
            line_total=120.0,
        )
        bill1.items.append(item1)
        bill1.total = 120.0

        # Bill 2
        bill2 = Bill(status=BillStatus.DRAFT, items=[])
        session.add(bill2)
        await session.flush()
        item2 = BillItem(
            bill_id=bill2.id,
            product_id=product.id,
            product_name=product.name,
            quantity=4.0,
            unit_price=30.0,
            line_total=120.0,
        )
        bill2.items.append(item2)
        bill2.total = 120.0

        await session.commit()
        bill1_id = bill1.id
        bill2_id = bill2.id
        prod_id = product.id

    # 2. Define worker functions executing in distinct sessions concurrently
    results = {"successes": 0, "failures": 0, "errors": []}

    async def finalize_worker(bill_id: int):
        async with session_factory() as worker_session:
            try:
                res = await bill_service.finalize_bill(worker_session, bill_id=bill_id)
                await worker_session.commit()
                results["successes"] += 1
                return ("SUCCESS", res)
            except InsufficientStockError as e:
                await worker_session.rollback()
                results["failures"] += 1
                results["errors"].append(str(e))
                return ("INSUFFICIENT_STOCK", str(e))
            except Exception as e:
                await worker_session.rollback()
                results["failures"] += 1
                results["errors"].append(str(e))
                return ("ERROR", str(e))

    # 3. Launch both coroutines simultaneously with asyncio.gather
    task1 = asyncio.create_task(finalize_worker(bill1_id))
    task2 = asyncio.create_task(finalize_worker(bill2_id))
    await asyncio.gather(task1, task2)

    # 4. Assert invariants
    assert results["successes"] == 1, f"Expected exactly 1 successful finalization, got {results['successes']}"
    assert results["failures"] == 1, f"Expected exactly 1 failed finalization, got {results['failures']}"
    assert any("Insufficient stock" in err for err in results["errors"])

    # 5. Verify final database state
    async with session_factory() as check_session:
        from sqlalchemy import select
        res = await check_session.execute(select(Product).where(Product.id == prod_id))
        final_prod = res.scalar_one()
        assert final_prod.stock_qty == 1.0, f"Expected final stock 1.0, got {final_prod.stock_qty}"

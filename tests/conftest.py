"""Pytest Test Configuration and Fixtures."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.db import Base
from app.inventory.models import Product
from app.billing.models import Bill, BillItem
from app.khata.models import Customer, KhataEntry
from app.preferences.models import OwnerPreference
from app.core.transactions import AuditLog
from app.core.idempotency import ProcessedUpdate

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create isolated in-memory test database engine."""
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    """Provide an isolated async database session for a test."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def seeded_session(db_session: AsyncSession):
    """Provide a session pre-populated with standard Kirana SKUs."""
    from app.scripts.seed import SEED_PRODUCTS, SEED_CUSTOMERS, SEED_PREFERENCES
    from app.khata.models import KhataType

    for p_data in SEED_PRODUCTS:
        db_session.add(Product(**p_data))

    for c_data in SEED_CUSTOMERS:
        cust = Customer(name=c_data["name"], phone=c_data["phone"])
        db_session.add(cust)
        await db_session.flush()
        if c_data["initial_credit"] > 0:
            db_session.add(
                KhataEntry(
                    customer_id=cust.id,
                    type=KhataType.CREDIT,
                    amount=c_data["initial_credit"],
                    note=c_data["note"],
                )
            )

    for k, v in SEED_PREFERENCES.items():
        db_session.add(OwnerPreference(key=k, value=str(v)))

    await db_session.commit()
    return db_session

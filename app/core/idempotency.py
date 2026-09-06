"""Idempotency tracking to prevent duplicate execution from Telegram update redeliveries."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, String, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Base


class ProcessedUpdate(Base):
    __tablename__ = "processed_updates"

    telegram_update_id = Column(String(100), primary_key=True)
    update_type = Column(String(50), default="message", nullable=False)
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self) -> str:
        return f"<ProcessedUpdate(id={self.telegram_update_id}, type={self.update_type})>"


async def is_update_processed(session: AsyncSession, update_id: str | int) -> bool:
    """Check if an update_id has already been processed."""
    uid = str(update_id)
    stmt = select(ProcessedUpdate).where(ProcessedUpdate.telegram_update_id == uid)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def mark_update_processed(
    session: AsyncSession,
    update_id: str | int,
    update_type: str = "message"
) -> ProcessedUpdate:
    """Record an update_id as processed."""
    uid = str(update_id)
    entry = ProcessedUpdate(
        telegram_update_id=uid,
        update_type=update_type,
        processed_at=datetime.now(timezone.utc),
    )
    session.add(entry)
    await session.flush()
    return entry

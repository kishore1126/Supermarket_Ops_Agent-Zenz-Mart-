"""Audit Log Model and Helper for tracking all state changes."""

from datetime import datetime, timezone
import json
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type = Column(String(50), nullable=False, index=True)
    reference_id = Column(String(100), nullable=True, index=True)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self) -> str:
        return f"<AuditLog(action={self.action_type}, ref={self.reference_id})>"


async def record_audit_log(
    session: AsyncSession,
    action_type: str,
    reference_id: str | None = None,
    payload: dict | None = None,
) -> AuditLog:
    """Record an action in the audit log inside the current transaction."""
    payload_str = json.dumps(payload) if payload is not None else None
    log_entry = AuditLog(
        action_type=action_type,
        reference_id=str(reference_id) if reference_id is not None else None,
        payload=payload_str,
    )
    session.add(log_entry)
    return log_entry

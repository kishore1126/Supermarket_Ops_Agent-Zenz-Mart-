"""Owner Preferences ORM Model for persistent store settings."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.core.db import Base


class OwnerPreference(Base):
    __tablename__ = "owner_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<OwnerPreference(key='{self.key}', value='{self.value}')>"

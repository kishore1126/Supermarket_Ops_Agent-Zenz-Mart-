"""Khata (Customer Credit Ledger) ORM Models."""

from datetime import datetime, timezone
import enum
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.core.db import Base


class KhataType(str, enum.Enum):
    CREDIT = "CREDIT"    # Customer took goods on credit (adds to balance owed)
    PAYMENT = "PAYMENT"  # Customer paid money (reduces balance owed)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    phone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    khata_entries = relationship("KhataEntry", back_populates="customer", cascade="all, delete-orphan", lazy="selectin")
    bills = relationship("Bill", back_populates="customer", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, name='{self.name}')>"


class KhataEntry(Base):
    __tablename__ = "khata_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum(KhataType), nullable=False)
    amount = Column(Float, nullable=False)
    bill_id = Column(Integer, ForeignKey("bills.id", ondelete="SET NULL"), nullable=True)
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    customer = relationship("Customer", back_populates="khata_entries")
    bill = relationship("Bill", lazy="selectin")

    def __repr__(self) -> str:
        return f"<KhataEntry(id={self.id}, customer_id={self.customer_id}, type={self.type}, amount=₹{self.amount:.2f})>"

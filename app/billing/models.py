"""Billing ORM Models: Bill, BillItem, and BillStatus."""

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
    Text,
)
from sqlalchemy.orm import relationship

from app.core.db import Base


class BillStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"
    CANCELLED = "CANCELLED"


class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    customer_name = Column(String(255), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    status = Column(Enum(BillStatus), default=BillStatus.DRAFT, nullable=False, index=True)
    
    subtotal = Column(Float, default=0.0, nullable=False)  # Taxable base sum
    cgst = Column(Float, default=0.0, nullable=False)
    sgst = Column(Float, default=0.0, nullable=False)
    round_off = Column(Float, default=0.0, nullable=False)  # Round-off adjustment in paise
    total = Column(Float, default=0.0, nullable=False)      # Final rounded payable
    
    payment_method = Column(String(50), default="UPI", nullable=False)  # UPI, Cash, Card, Khata
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    finalized_at = Column(DateTime, nullable=True)

    # Relationships
    items = relationship("BillItem", back_populates="bill", cascade="all, delete-orphan", lazy="selectin")
    customer = relationship("Customer", back_populates="bills", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Bill(id={self.id}, status={self.status}, total=₹{self.total:.2f})>"


class BillItem(Base):
    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_id = Column(Integer, ForeignKey("bills.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    product_name = Column(String(255), nullable=False)
    unit = Column(String(50), nullable=False, default="packet")
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)  # MRP / selling price per unit
    gst_rate = Column(Float, nullable=False, default=0.0)
    hsn_code = Column(String(50), nullable=False, default="0000")
    taxable_value = Column(Float, nullable=False, default=0.0)
    cgst_amount = Column(Float, nullable=False, default=0.0)
    sgst_amount = Column(Float, nullable=False, default=0.0)
    tax_amount = Column(Float, nullable=False, default=0.0)
    line_total = Column(Float, nullable=False, default=0.0)

    # Relationships
    bill = relationship("Bill", back_populates="items")
    product = relationship("Product", lazy="selectin")

    def __repr__(self) -> str:
        return f"<BillItem(id={self.id}, item='{self.product_name}', qty={self.quantity}, total=₹{self.line_total:.2f})>"

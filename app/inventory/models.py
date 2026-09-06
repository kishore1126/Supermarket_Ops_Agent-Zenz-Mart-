"""Product Inventory ORM Model."""

from datetime import datetime, timezone
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Boolean,
)
from app.core.db import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    unit = Column(String(50), nullable=False, default="packet")  # kg, g, litre, ml, packet, piece, dozen
    cost_price = Column(Float, nullable=False)
    selling_price = Column(Float, nullable=False)
    mrp = Column(Float, nullable=False)
    gst_rate = Column(Float, nullable=False, default=0.0)  # e.g. 0.0, 0.05, 0.12, 0.18
    hsn_code = Column(String(50), nullable=False, default="0000")
    stock_qty = Column(Float, nullable=False, default=0.0)
    reorder_level = Column(Float, nullable=False, default=5.0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("stock_qty >= 0", name="check_stock_non_negative"),
        Index("idx_product_name_stock", "name", "stock_qty"),
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name='{self.name}', stock={self.stock_qty} {self.unit})>"

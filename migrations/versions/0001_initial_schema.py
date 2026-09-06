"""Initial Kirana Store Schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-06 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. products table
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False, server_default="packet"),
        sa.Column("cost_price", sa.Float(), nullable=False),
        sa.Column("selling_price", sa.Float(), nullable=False),
        sa.Column("mrp", sa.Float(), nullable=False),
        sa.Column("gst_rate", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("hsn_code", sa.String(length=50), nullable=False, server_default="0000"),
        sa.Column("stock_qty", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("reorder_level", sa.Float(), nullable=False, server_default="5.0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("stock_qty >= 0", name="check_stock_non_negative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_name", "products", ["name"], unique=True)
    op.create_index("idx_product_name_stock", "products", ["name", "stock_qty"])

    # 2. customers table
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customers_name", "customers", ["name"], unique=True)

    # 3. bills table
    op.create_table(
        "bills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("customer_phone", sa.String(length=50), nullable=True),
        sa.Column("status", sa.Enum("DRAFT", "FINALIZED", "CANCELLED", name="billstatus"), nullable=False, server_default="DRAFT"),
        sa.Column("subtotal", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("cgst", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("sgst", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("round_off", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("payment_method", sa.String(length=50), nullable=False, server_default="UPI"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finalized_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bills_status", "bills", ["status"])

    # 4. bill_items table
    op.create_table(
        "bill_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bill_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False, server_default="packet"),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("gst_rate", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("hsn_code", sa.String(length=50), nullable=False, server_default="0000"),
        sa.Column("taxable_value", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("cgst_amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("sgst_amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("tax_amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("line_total", sa.Float(), nullable=False, server_default="0.0"),
        sa.ForeignKeyConstraint(["bill_id"], ["bills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bill_items_bill_id", "bill_items", ["bill_id"])
    op.create_index("ix_bill_items_product_id", "bill_items", ["product_id"])

    # 5. khata_entries table
    op.create_table(
        "khata_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.Enum("CREDIT", "PAYMENT", name="khatatype"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("bill_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bill_id"], ["bills.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_khata_entries_customer_id", "khata_entries", ["customer_id"])

    # 6. owner_preferences table
    op.create_table(
        "owner_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_owner_preferences_key", "owner_preferences", ["key"], unique=True)

    # 7. processed_updates table (idempotency)
    op.create_table(
        "processed_updates",
        sa.Column("telegram_update_id", sa.String(length=100), nullable=False),
        sa.Column("update_type", sa.String(length=50), nullable=False, server_default="message"),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("telegram_update_id"),
    )

    # 8. audit_log table
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("reference_id", sa.String(length=100), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_action_type", "audit_log", ["action_type"])
    op.create_index("ix_audit_log_reference_id", "audit_log", ["reference_id"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("processed_updates")
    op.drop_table("owner_preferences")
    op.drop_table("khata_entries")
    op.drop_table("bill_items")
    op.drop_table("bills")
    op.drop_table("customers")
    op.drop_table("products")

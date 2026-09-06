"""Database Seed Script: Populates realistic Indian Kirana Store SKUs, Khata Customers, and Preferences."""

import asyncio
import sys
from sqlalchemy import select
from app.core.db import get_db_session, init_db
from app.core.transactions import AuditLog
from app.core.idempotency import ProcessedUpdate
from app.inventory.models import Product
from app.billing.models import Bill, BillItem
from app.khata.models import Customer, KhataEntry, KhataType
from app.preferences.models import OwnerPreference
from app.config import settings

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SEED_PRODUCTS = [
    {
        "name": "Aashirvaad Atta 5kg",
        "unit": "packet",
        "cost_price": 210.0,
        "selling_price": 245.0,
        "mrp": 260.0,
        "gst_rate": 0.05,  # 5% GST on branded packaged flour
        "hsn_code": "1101",
        "stock_qty": 20.0,
        "reorder_level": 5.0,
    },
    {
        "name": "Loose Wheat Atta",
        "unit": "kg",
        "cost_price": 32.0,
        "selling_price": 38.0,
        "mrp": 40.0,
        "gst_rate": 0.00,  # 0% GST on loose staple
        "hsn_code": "1101",
        "stock_qty": 100.0,
        "reorder_level": 20.0,
    },
    {
        "name": "Tata Salt 1kg",
        "unit": "packet",
        "cost_price": 22.0,
        "selling_price": 28.0,
        "mrp": 30.0,
        "gst_rate": 0.05,
        "hsn_code": "2501",
        "stock_qty": 50.0,
        "reorder_level": 10.0,
    },
    {
        "name": "Amul Butter 100g",
        "unit": "packet",
        "cost_price": 50.0,
        "selling_price": 58.0,
        "mrp": 60.0,
        "gst_rate": 0.12,  # 12% GST on butter/dairy FMCG
        "hsn_code": "0405",
        "stock_qty": 30.0,
        "reorder_level": 8.0,
    },
    {
        "name": "Fortune Sunflower Oil 1L",
        "unit": "pouch",
        "cost_price": 125.0,
        "selling_price": 145.0,
        "mrp": 155.0,
        "gst_rate": 0.05,  # 5% GST on edible oil
        "hsn_code": "1512",
        "stock_qty": 40.0,
        "reorder_level": 10.0,
    },
    {
        "name": "Maggi 70g",
        "unit": "packet",
        "cost_price": 12.0,
        "selling_price": 14.0,
        "mrp": 14.0,
        "gst_rate": 0.12,  # 12% GST on instant noodles
        "hsn_code": "1902",
        "stock_qty": 150.0,
        "reorder_level": 25.0,
    },
    {
        "name": "Parle-G 250g",
        "unit": "packet",
        "cost_price": 24.0,
        "selling_price": 28.0,
        "mrp": 30.0,
        "gst_rate": 0.18,  # 18% GST on biscuits
        "hsn_code": "1905",
        "stock_qty": 60.0,
        "reorder_level": 15.0,
    },
    {
        "name": "Surf Excel Quick Wash 1kg",
        "unit": "packet",
        "cost_price": 135.0,
        "selling_price": 155.0,
        "mrp": 170.0,
        "gst_rate": 0.18,  # 18% GST on detergent
        "hsn_code": "3402",
        "stock_qty": 25.0,
        "reorder_level": 5.0,
    },
    {
        "name": "Loose Sugar",
        "unit": "kg",
        "cost_price": 38.0,
        "selling_price": 44.0,
        "mrp": 46.0,
        "gst_rate": 0.00,  # 0% GST on loose sugar
        "hsn_code": "1701",
        "stock_qty": 80.0,
        "reorder_level": 15.0,
    },
    {
        "name": "Loose Basmati Rice",
        "unit": "kg",
        "cost_price": 75.0,
        "selling_price": 90.0,
        "mrp": 95.0,
        "gst_rate": 0.00,  # 0% GST on loose rice
        "hsn_code": "1006",
        "stock_qty": 60.0,
        "reorder_level": 15.0,
    },
    {
        "name": "Loose Toor Dal",
        "unit": "kg",
        "cost_price": 130.0,
        "selling_price": 155.0,
        "mrp": 160.0,
        "gst_rate": 0.00,  # 0% GST on loose dal
        "hsn_code": "0713",
        "stock_qty": 45.0,
        "reorder_level": 10.0,
    },
]

SEED_CUSTOMERS = [
    {"name": "Ramesh Kumar", "phone": "+91 98230 11223", "initial_credit": 500.0, "note": "Monthly ration credit"},
    {"name": "Suresh Patel", "phone": "+91 98450 33445", "initial_credit": 0.0, "note": None},
    {"name": "Priya Sharma", "phone": "+91 97110 55667", "initial_credit": 200.0, "note": "Milk & butter credit"},
]

SEED_PREFERENCES = {
    "shop_name": settings.DEFAULT_SHOP_NAME,
    "shop_gstin": settings.DEFAULT_SHOP_GSTIN,
    "shop_address": settings.DEFAULT_SHOP_ADDRESS,
    "shop_phone": settings.DEFAULT_SHOP_PHONE,
    "default_payment_method": settings.DEFAULT_PAYMENT_METHOD,
    "preferred_atta_brand": "Aashirvaad Atta 5kg",
}


async def seed_database():
    """Seed products, customers, khata entries, and default preferences."""
    print("🌱 Initializing Database tables...")
    await init_db()

    async with get_db_session() as session:
        # 1. Seed Products
        print("📦 Seeding Products...")
        for p_data in SEED_PRODUCTS:
            stmt = select(Product).where(Product.name == p_data["name"])
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if not existing:
                product = Product(**p_data)
                session.add(product)
                print(f"  + Added SKU: {p_data['name']} (Stock: {p_data['stock_qty']} {p_data['unit']})")
            else:
                # Update existing fields
                for k, v in p_data.items():
                    setattr(existing, k, v)
                print(f"  ~ Updated SKU: {p_data['name']}")

        # 2. Seed Customers & Khata
        print("👤 Seeding Khata Customers...")
        for c_data in SEED_CUSTOMERS:
            stmt = select(Customer).where(Customer.name == c_data["name"])
            res = await session.execute(stmt)
            existing_c = res.scalar_one_or_none()
            if not existing_c:
                cust = Customer(name=c_data["name"], phone=c_data["phone"])
                session.add(cust)
                await session.flush()
                print(f"  + Added Customer: {cust.name}")

                if c_data["initial_credit"] > 0:
                    entry = KhataEntry(
                        customer_id=cust.id,
                        type=KhataType.CREDIT,
                        amount=c_data["initial_credit"],
                        note=c_data["note"] or "Opening balance",
                    )
                    session.add(entry)
                    print(f"    -> Opening credit: ₹{c_data['initial_credit']:.2f}")
            else:
                print(f"  ~ Customer exists: {existing_c.name}")

        # 3. Seed Preferences
        print("⚙️ Seeding Owner Preferences...")
        for k, v in SEED_PREFERENCES.items():
            stmt = select(OwnerPreference).where(OwnerPreference.key == k)
            res = await session.execute(stmt)
            pref = res.scalar_one_or_none()
            if not pref:
                pref = OwnerPreference(key=k, value=str(v))
                session.add(pref)
                print(f"  + Set preference [{k}] = '{v}'")
            else:
                pref.value = str(v)
                print(f"  ~ Updated preference [{k}] = '{v}'")

        await session.commit()
    print("✅ Database seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_database())

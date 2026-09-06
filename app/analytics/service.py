"""Analytics Service: Daily close aggregation, payment method breakdowns, and multi-day sales trends using Pandas."""

from datetime import datetime, date, time, timedelta, timezone
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models import Bill, BillItem, BillStatus


async def get_daily_close(
    session: AsyncSession,
    target_date: str | date | None = None,
) -> dict:
    """
    Compute daily store closing figures for a given date (defaults to today).
    
    Includes:
      - Total gross revenue, taxable subtotal, total tax (CGST + SGST)
      - Payment breakdown (Cash, UPI, Card, Khata)
      - Bill count and average ticket size
      - Top selling products
    """
    if target_date is None:
        close_date = datetime.now(timezone.utc).date()
    elif isinstance(target_date, str):
        try:
            close_date = datetime.strptime(target_date.strip(), "%Y-%m-%d").date()
        except ValueError:
            close_date = datetime.now(timezone.utc).date()
    else:
        close_date = target_date

    start_dt = datetime.combine(close_date, time.min)
    end_dt = datetime.combine(close_date, time.max)

    # Fetch finalized bills for the day
    stmt = (
        select(Bill)
        .options(selectinload(Bill.items))
        .where(
            Bill.status == BillStatus.FINALIZED,
            Bill.created_at >= start_dt,
            Bill.created_at <= end_dt,
        )
    )
    res = await session.execute(stmt)
    bills = res.scalars().all()

    if not bills:
        return {
            "date": close_date.isoformat(),
            "total_bills": 0,
            "total_sales": 0.0,
            "taxable_subtotal": 0.0,
            "total_cgst": 0.0,
            "total_sgst": 0.0,
            "total_tax": 0.0,
            "round_off": 0.0,
            "avg_bill_value": 0.0,
            "payment_breakdown": {"UPI": 0.0, "CASH": 0.0, "CARD": 0.0, "KHATA": 0.0},
            "top_items": [],
            "message": f"No finalized sales recorded for {close_date.isoformat()}."
        }

    # Use Pandas for robust tabular aggregation
    bills_data = [
        {
            "id": b.id,
            "subtotal": b.subtotal,
            "cgst": b.cgst,
            "sgst": b.sgst,
            "round_off": b.round_off,
            "total": b.total,
            "payment_method": b.payment_method.upper(),
        }
        for b in bills
    ]
    df_bills = pd.DataFrame(bills_data)

    total_bills = len(df_bills)
    total_sales = float(df_bills["total"].sum())
    taxable_subtotal = float(df_bills["subtotal"].sum())
    total_cgst = float(df_bills["cgst"].sum())
    total_sgst = float(df_bills["sgst"].sum())
    total_tax = round(total_cgst + total_sgst, 2)
    total_round_off = float(df_bills["round_off"].sum())
    avg_bill_value = round(total_sales / total_bills, 2) if total_bills > 0 else 0.0

    # Payment breakdown
    pay_series = df_bills.groupby("payment_method")["total"].sum().to_dict()
    payment_breakdown = {
        "UPI": round(pay_series.get("UPI", 0.0), 2),
        "CASH": round(pay_series.get("CASH", 0.0), 2),
        "CARD": round(pay_series.get("CARD", 0.0), 2),
        "KHATA": round(pay_series.get("KHATA", 0.0), 2),
    }

    # Item breakdown
    all_items = []
    for b in bills:
        for item in b.items:
            all_items.append({
                "name": item.product_name,
                "unit": item.unit,
                "quantity": item.quantity,
                "revenue": item.line_total,
            })
    
    top_items = []
    if all_items:
        df_items = pd.DataFrame(all_items)
        item_agg = df_items.groupby(["name", "unit"]).agg({"quantity": "sum", "revenue": "sum"}).reset_index()
        item_agg = item_agg.sort_values(by="revenue", ascending=False).head(5)
        top_items = [
            {
                "product_name": row["name"],
                "unit": row["unit"],
                "quantity_sold": float(row["quantity"]),
                "revenue": round(float(row["revenue"]), 2),
            }
            for _, row in item_agg.iterrows()
        ]

    return {
        "date": close_date.isoformat(),
        "total_bills": total_bills,
        "total_sales": round(total_sales, 2),
        "taxable_subtotal": round(taxable_subtotal, 2),
        "total_cgst": round(total_cgst, 2),
        "total_sgst": round(total_sgst, 2),
        "total_tax": total_tax,
        "round_off": round(total_round_off, 2),
        "avg_bill_value": avg_bill_value,
        "payment_breakdown": payment_breakdown,
        "top_items": top_items,
        "message": f"Daily Close for {close_date.isoformat()}: Total ₹{total_sales:.2f} across {total_bills} bills."
    }


async def get_sales_analysis(
    session: AsyncSession,
    days: int = 7,
) -> dict:
    """Analyze store performance over the past N days."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = (
        select(Bill)
        .options(selectinload(Bill.items))
        .where(
            Bill.status == BillStatus.FINALIZED,
            Bill.created_at >= cutoff_date,
        )
    )
    res = await session.execute(stmt)
    bills = res.scalars().all()

    if not bills:
        return {
            "period_days": days,
            "total_revenue": 0.0,
            "total_bills": 0,
            "daily_trends": [],
            "top_products": [],
            "payment_methods": {},
            "message": f"No sales data available for the past {days} days."
        }

    # Aggregate daily trends
    bill_records = [
        {
            "date": b.created_at.strftime("%Y-%m-%d"),
            "total": b.total,
            "tax": b.cgst + b.sgst,
            "payment": b.payment_method.upper(),
        }
        for b in bills
    ]
    df_bills = pd.DataFrame(bill_records)
    daily_grp = df_bills.groupby("date").agg({"total": "sum", "date": "count"}).rename(columns={"date": "bill_count"}).reset_index()
    daily_trends = [
        {
            "date": row["date"],
            "revenue": round(float(row["total"]), 2),
            "bills": int(row["bill_count"]),
        }
        for _, row in daily_grp.iterrows()
    ]

    # Top products
    item_records = [
        {"name": item.product_name, "qty": item.quantity, "revenue": item.line_total, "gst_rate": f"{int(item.gst_rate*100)}%"}
        for b in bills
        for item in b.items
    ]
    df_items = pd.DataFrame(item_records)
    item_grp = df_items.groupby(["name", "gst_rate"]).agg({"qty": "sum", "revenue": "sum"}).reset_index()
    item_grp = item_grp.sort_values(by="revenue", ascending=False).head(5)
    top_products = [
        {
            "name": row["name"],
            "gst_rate": row["gst_rate"],
            "quantity_sold": float(row["qty"]),
            "revenue": round(float(row["revenue"]), 2),
        }
        for _, row in item_grp.iterrows()
    ]

    # Payment distribution
    pay_dist = df_bills.groupby("payment")["total"].sum().to_dict()
    total_rev = float(df_bills["total"].sum())

    return {
        "period_days": days,
        "total_revenue": round(total_rev, 2),
        "total_bills": len(bills),
        "daily_trends": daily_trends,
        "top_products": top_products,
        "payment_methods": {k: round(float(v), 2) for k, v in pay_dist.items()},
        "message": f"Sales analysis for last {days} days: ₹{total_rev:.2f} total revenue from {len(bills)} bills."
    }

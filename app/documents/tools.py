"""Document Generation Tools exposed to the Agent."""

from pathlib import Path
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tool_registry import registry
from app.billing import service as billing_service
from app.analytics import service as analytics_service
from app.inventory import service as inventory_service
from app.preferences import service as pref_service
from app.documents.invoice_pdf import generate_invoice_pdf
from app.documents.analysis_pptx import generate_analysis_deck


from typing import Literal


class GenerateInvoicePdfInput(BaseModel):
    bill_id: int | None = Field(
        None,
        description="Optional specific bill ID (e.g. 1, 2, 4) if requested.",
    )
    order: Literal["first", "last", "specific"] = Field(
        "last",
        description="Selector order: 'first' (or earliest/oldest), 'last' (or latest/most recent/previous), or 'specific' if a bill_id is provided.",
    )


class GenerateAnalysisDeckInput(BaseModel):
    days: int = Field(
        7,
        description="Number of past days of sales data to compile into the PPTX slide deck (default 7).",
    )


@registry.register(
    name="generate_invoice_pdf",
    description="Generate a clean, GST-compliant PDF invoice document for a bill (first, last/most recent, or specific bill ID).",
    schema=GenerateInvoicePdfInput,
)
async def generate_invoice_pdf_tool(
    session: AsyncSession,
    bill_id: int | None = None,
    order: str = "last",
    **kwargs,
) -> dict:
    try:
        bill = await billing_service.get_bill_by_selector(session, bill_id=bill_id, order=order)
        if not bill:
            return {"error": f"Could not find any bill matching selector order='{order}', bill_id={bill_id}."}

        bill_data = await billing_service.preview_bill(session, bill_id=bill.id)
        if "error" in bill_data:
            return {"error": f"Error loading bill #{bill.id}: {bill_data['error']}"}

        # Fetch shop details from preferences
        shop_prefs = await pref_service.get_all_preferences(session)

        pdf_path = generate_invoice_pdf(
            bill_data=bill_data,
            shop_info=shop_prefs,
        )

        date_str = bill_data.get("created_at", "")[:10]
        return {
            "success": True,
            "bill_id": bill_data["bill_id"],
            "file_path": pdf_path,
            "file_name": Path(pdf_path).name,
            "total": bill_data["total"],
            "created_at": date_str,
            "message": f"Generated GST Tax Invoice PDF for Bill #{bill_data['bill_id']} dated {date_str} ({Path(pdf_path).name})."
        }
    except Exception as e:
        return {"error": f"Failed to generate invoice PDF: {str(e)}"}


@registry.register(
    name="generate_analysis_deck",
    description="Generate an executive PowerPoint (.pptx) presentation deck analyzing store sales, top SKUs, and stock health with charts.",
    schema=GenerateAnalysisDeckInput,
)
async def generate_analysis_deck_tool(
    session: AsyncSession,
    days: int = 7,
    **kwargs,
) -> dict:
    try:
        sales_data = await analytics_service.get_sales_analysis(session, days=days)
        low_stock_items = await inventory_service.get_low_stock(session)
        shop_prefs = await pref_service.get_all_preferences(session)

        pptx_path = generate_analysis_deck(
            sales_data=sales_data,
            low_stock_items=low_stock_items,
            shop_info=shop_prefs,
        )

        return {
            "success": True,
            "file_path": pptx_path,
            "file_name": Path(pptx_path).name,
            "period_days": days,
            "total_revenue": sales_data.get("total_revenue", 0.0),
            "message": f"Generated {days}-day Sales Analysis PowerPoint presentation ({Path(pptx_path).name})."
        }
    except Exception as e:
        return {"error": f"Failed to generate analysis deck: {str(e)}"}

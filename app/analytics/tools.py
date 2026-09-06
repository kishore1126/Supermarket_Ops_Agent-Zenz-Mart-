"""Analytics Tools exposed to the Agent."""

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tool_registry import registry
from app.analytics import service


class DailyCloseInput(BaseModel):
    date_str: str | None = Field(
        None,
        description="Target date in 'YYYY-MM-DD' format (e.g. '2026-09-06'). Defaults to today.",
    )


class SalesAnalysisInput(BaseModel):
    days: int = Field(
        7,
        description="Number of past days to analyze (default 7 for weekly analysis).",
    )


@registry.register(
    name="get_daily_close",
    description="Compute store daily close: total sales, taxes collected, payment method breakdown (Cash vs UPI), and top items.",
    schema=DailyCloseInput,
)
async def get_daily_close_tool(
    session: AsyncSession,
    date_str: str | None = None,
    **kwargs,
) -> dict:
    try:
        res = await service.get_daily_close(session, target_date=date_str)
        return res
    except Exception as e:
        return {"error": str(e)}


@registry.register(
    name="get_sales_analysis",
    description="Analyze store sales performance, revenue trends, top SKUs, and payment shares over the past N days.",
    schema=SalesAnalysisInput,
)
async def get_sales_analysis_tool(
    session: AsyncSession,
    days: int = 7,
    **kwargs,
) -> dict:
    try:
        res = await service.get_sales_analysis(session, days=days)
        return res
    except Exception as e:
        return {"error": str(e)}

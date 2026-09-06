"""Owner Preferences Tools exposed to the Agent."""

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tool_registry import registry
from app.preferences import service


class SetPreferenceInput(BaseModel):
    key: str = Field(
        ...,
        description="Preference key (e.g. 'default_payment_method', 'preferred_atta_brand', 'shop_name', 'shop_gstin').",
    )
    value: str = Field(
        ...,
        description="Setting value to remember (e.g. 'UPI', 'Aashirvaad Atta 5kg', 'Maa Durga Kirana').",
    )


class GetPreferencesInput(BaseModel):
    pass


@registry.register(
    name="set_preference",
    description="Save a standing owner preference or store setting that permanently persists across /new chats.",
    schema=SetPreferenceInput,
)
async def set_preference_tool(
    session: AsyncSession,
    key: str,
    value: str,
    **kwargs,
) -> dict:
    try:
        res = await service.set_preference(session, key=key, value=value)
        await session.commit()
        return res
    except Exception as e:
        await session.rollback()
        return {"error": str(e)}


@registry.register(
    name="get_preferences",
    description="Retrieve all current stored owner preferences and store configuration values.",
    schema=GetPreferencesInput,
)
async def get_preferences_tool(
    session: AsyncSession,
    **kwargs,
) -> dict:
    try:
        prefs = await service.get_all_preferences(session)
        return {"preferences": prefs}
    except Exception as e:
        return {"error": str(e)}

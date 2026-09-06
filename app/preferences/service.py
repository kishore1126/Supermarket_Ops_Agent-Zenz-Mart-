"""Owner Preferences Service: Durable store settings and shopkeeper memory across chats."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.preferences.models import OwnerPreference
from app.core.transactions import record_audit_log
from app.config import settings

# Default Fallback Values
DEFAULT_PREFERENCES = {
    "shop_name": settings.DEFAULT_SHOP_NAME,
    "shop_gstin": settings.DEFAULT_SHOP_GSTIN,
    "shop_address": settings.DEFAULT_SHOP_ADDRESS,
    "shop_phone": settings.DEFAULT_SHOP_PHONE,
    "default_payment_method": settings.DEFAULT_PAYMENT_METHOD,
    "preferred_atta_brand": "Aashirvaad Atta 5kg",
}


async def get_preference(
    session: AsyncSession,
    key: str,
    default: str | None = None,
) -> str | None:
    """Get a single preference value by key."""
    clean_key = key.strip().lower()
    stmt = select(OwnerPreference).where(OwnerPreference.key == clean_key)
    res = await session.execute(stmt)
    pref = res.scalar_one_or_none()
    if pref:
        return pref.value
    return default if default is not None else DEFAULT_PREFERENCES.get(clean_key)


async def get_all_preferences(session: AsyncSession) -> dict[str, str]:
    """Retrieve all store preferences with fallback to system defaults."""
    stmt = select(OwnerPreference)
    res = await session.execute(stmt)
    db_prefs = res.scalars().all()

    prefs = dict(DEFAULT_PREFERENCES)
    for p in db_prefs:
        prefs[p.key] = p.value
    return prefs


async def set_preference(
    session: AsyncSession,
    key: str,
    value: str,
) -> dict:
    """Set or update a persistent preference key-value pair."""
    clean_key = key.strip().lower()
    clean_val = value.strip()

    stmt = select(OwnerPreference).where(OwnerPreference.key == clean_key)
    res = await session.execute(stmt)
    pref = res.scalar_one_or_none()

    if not pref:
        pref = OwnerPreference(key=clean_key, value=clean_val)
        session.add(pref)
    else:
        pref.value = clean_val

    await session.flush()

    await record_audit_log(
        session,
        action_type="PREFERENCE_UPDATE",
        reference_id=f"pref_{clean_key}",
        payload={"key": clean_key, "value": clean_val},
    )

    return {
        "success": True,
        "key": clean_key,
        "value": clean_val,
        "message": f"Saved preference: '{clean_key}' is now set to '{clean_val}' (persists across chats)."
    }

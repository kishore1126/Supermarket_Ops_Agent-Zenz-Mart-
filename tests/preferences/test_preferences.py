"""Unit tests for Owner Preferences Feature."""

import pytest
from app.preferences import service
from app.agent.tool_registry import registry
import app.preferences.tools


@pytest.mark.asyncio
async def test_get_seeded_preferences(seeded_session):
    prefs = await service.get_all_preferences(seeded_session)
    assert prefs["shop_name"] == "Zenz Mart"
    assert prefs["default_payment_method"] == "UPI"
    assert prefs["preferred_atta_brand"] == "Aashirvaad Atta 5kg"


@pytest.mark.asyncio
async def test_set_and_update_preference(seeded_session):
    # Set custom preference
    set_res = await service.set_preference(
        session=seeded_session,
        key="default_payment_method",
        value="Cash",
    )
    assert set_res["success"] is True
    assert set_res["value"] == "Cash"

    # Verify retrieval
    val = await service.get_preference(seeded_session, "default_payment_method")
    assert val == "Cash"


@pytest.mark.asyncio
async def test_preferences_tool_registry(seeded_session):
    # Set via tool
    res = await registry.execute(
        name="set_preference",
        session=seeded_session,
        arguments={"key": "preferred_oil_brand", "value": "Fortune Sunflower Oil 1L"},
    )
    assert "error" not in res
    assert res["success"] is True

    # Get via tool
    get_res = await registry.execute(
        name="get_preferences",
        session=seeded_session,
        arguments={},
    )
    assert "error" not in get_res
    assert get_res["preferences"]["preferred_oil_brand"] == "Fortune Sunflower Oil 1L"

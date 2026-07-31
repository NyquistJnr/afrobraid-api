from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.braiders import repository as braiders_repo
from app.modules.braiders.models import OnboardingStep
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token

pytestmark = pytest.mark.asyncio

STYLES_URL = "/api/v1/admin/styles"
SERVICES_URL = "/api/v1/braiders/onboarding/services"
STATUS_URL = "/api/v1/braiders/onboarding/status"


async def _published_style_with_variation_and_addon(client: AsyncClient, admin_headers: dict) -> dict:
    style_resp = await client.post(STYLES_URL, json={"name": "Knotless Braids"}, headers=admin_headers)
    style = style_resp.json()["data"]
    await client.put(f"{STYLES_URL}/{style['id']}", json={"is_active": True}, headers=admin_headers)

    variation_resp = await client.post(
        f"{STYLES_URL}/{style['id']}/variations",
        json={"name": "Mid-back length"},
        headers=admin_headers,
    )
    variation = variation_resp.json()["data"]

    addon_resp = await client.post(
        "/api/v1/admin/addons", json={"name": "Beads"}, headers=admin_headers
    )
    addon = addon_resp.json()["data"]

    return {"style_id": style["id"], "variation_id": variation["id"], "addon_id": addon["id"]}


async def test_braider_selects_a_style_and_completes_service_type_step(
    client: AsyncClient, db_session: AsyncSession
):
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    catalog = await _published_style_with_variation_and_addon(client, admin_headers)

    braider, braider_token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    braider_headers = {"Authorization": f"Bearer {braider_token}"}

    # Realistically the braider only reaches this step after BUSINESS_INFO,
    # PHONE_VERIFICATION, and VERIFF are done - simulate that instead of
    # starting fresh, so the SERVICE_TYPE -> PORTFOLIO transition is testable.
    onboarding_status = await braiders_repo.create_onboarding_status_for_user(db_session, braider.id)
    now = datetime.now(UTC)
    onboarding_status.business_info_completed_at = now
    onboarding_status.phone_verification_completed_at = now
    onboarding_status.veriff_completed_at = now
    onboarding_status.current_step = OnboardingStep.SERVICE_TYPE
    await db_session.commit()

    create_resp = await client.post(
        SERVICES_URL,
        json={
            "style_id": catalog["style_id"],
            "base_price": "180.00",
            "duration_minutes": 240,
            "variations": [{"style_variation_id": catalog["variation_id"], "price": "200.00"}],
            "addons": [{"addon_id": catalog["addon_id"], "price": "20.00", "is_required": False}],
        },
        headers=braider_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    body = create_resp.json()["data"]
    assert body["style_name_en"] == "Knotless Braids"
    assert body["base_price"] == "180.00"
    assert len(body["variations"]) == 1
    assert body["variations"][0]["price"] == "200.00"
    assert len(body["addons"]) == 1
    assert body["addons"][0]["price"] == "20.00"

    status_resp = await client.get(STATUS_URL, headers=braider_headers)
    status_data = status_resp.json()["data"]
    assert status_data["current_step"] == "PORTFOLIO"
    assert status_data["service_type_completed_at"] is not None

    list_resp = await client.get(SERVICES_URL, headers=braider_headers)
    list_data = list_resp.json()["data"]
    assert len(list_data["items"]) == 1
    assert list_data["pagination"]["total_items"] == 1

    get_resp = await client.get(f"{SERVICES_URL}/{body['id']}", headers=braider_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["id"] == body["id"]
    assert get_resp.json()["data"]["style_name_en"] == "Knotless Braids"

    duplicate_resp = await client.post(
        SERVICES_URL, json={"style_id": catalog["style_id"], "base_price": "100.00"}, headers=braider_headers
    )
    assert duplicate_resp.status_code == 409
    assert duplicate_resp.json()["error"]["code"] == "BRAIDER_STYLE_ALREADY_EXISTS"

    braider_style_id = body["id"]
    update_resp = await client.put(
        f"{SERVICES_URL}/{braider_style_id}", json={"base_price": "190.00"}, headers=braider_headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["base_price"] == "190.00"

    delete_resp = await client.delete(f"{SERVICES_URL}/{braider_style_id}", headers=braider_headers)
    assert delete_resp.status_code == 204

    list_after_delete = await client.get(SERVICES_URL, headers=braider_headers)
    assert list_after_delete.json()["data"]["items"] == []

    get_after_delete = await client.get(f"{SERVICES_URL}/{braider_style_id}", headers=braider_headers)
    assert get_after_delete.status_code == 404
    assert get_after_delete.json()["error"]["code"] == "BRAIDER_STYLE_NOT_FOUND"


async def test_cannot_select_an_unpublished_style(client: AsyncClient, db_session: AsyncSession):
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    style_resp = await client.post(
        STYLES_URL, json={"name": "Draft Style"}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    style_id = style_resp.json()["data"]["id"]

    _, braider_token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    resp = await client.post(
        SERVICES_URL,
        json={"style_id": style_id, "base_price": "50.00"},
        headers={"Authorization": f"Bearer {braider_token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "STYLE_NOT_ACTIVE"


async def test_get_by_id_is_scoped_to_the_owning_braider(
    client: AsyncClient, db_session: AsyncSession
):
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    catalog = await _published_style_with_variation_and_addon(client, admin_headers)

    _, owner_token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    create_resp = await client.post(
        SERVICES_URL,
        json={"style_id": catalog["style_id"], "base_price": "180.00"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    braider_style_id = create_resp.json()["data"]["id"]

    _, other_token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    resp = await client.get(
        f"{SERVICES_URL}/{braider_style_id}", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "BRAIDER_STYLE_NOT_FOUND"


async def test_bare_id_in_variations_gives_an_actionable_error(
    client: AsyncClient, db_session: AsyncSession
):
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    catalog = await _published_style_with_variation_and_addon(client, admin_headers)

    _, braider_token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)

    # The exact mistake a tester made against Swagger: passing bare ID
    # strings instead of {"style_variation_id"/"addon_id": ..., "price": ...}.
    resp = await client.post(
        SERVICES_URL,
        json={
            "style_id": catalog["style_id"],
            "base_price": "180.00",
            "variations": [catalog["variation_id"]],
            "addons": [catalog["addon_id"]],
        },
        headers={"Authorization": f"Bearer {braider_token}"},
    )
    assert resp.status_code == 422
    details = resp.json()["error"]["details"]
    messages = " ".join(d["msg"] for d in details)
    assert "style_variation_id" in messages
    assert "addon_id" in messages
    assert "bare ID string" in messages

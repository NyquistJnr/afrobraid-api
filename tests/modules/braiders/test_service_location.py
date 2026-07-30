import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.braiders import repository as braiders_repo
from app.modules.braiders.models import OnboardingStep
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token

pytestmark = pytest.mark.asyncio

LOCATION_URL = "/api/v1/braiders/onboarding/service-location"
STATUS_URL = "/api/v1/braiders/onboarding/status"


async def _put(client: AsyncClient, headers: dict, payload: dict) -> dict:
    resp = await client.put(LOCATION_URL, json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _set_step_to_service_location(db_session: AsyncSession, braider_id) -> None:
    onboarding_status = await braiders_repo.create_onboarding_status_for_user(db_session, braider_id)
    onboarding_status.current_step = OnboardingStep.SERVICE_LOCATION
    await db_session.commit()


async def test_get_returns_empty_state_when_unset(client: AsyncClient, db_session: AsyncSession):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    resp = await client.get(LOCATION_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["location_type"] is None
    assert data["offers_mobile"] is False
    assert data["is_complete"] is False


async def test_home_studio_completes_the_step(client: AsyncClient, db_session: AsyncSession):
    braider, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}
    await _set_step_to_service_location(db_session, braider.id)

    data = await _put(
        client,
        headers,
        {
            "location_type": "HOME_STUDIO",
            "address_line1": "Musterstrasse 12",
            "city": "Berlin",
            "postal_code": "10115",
            "country": "de",
            "latitude": "52.531677",
            "longitude": "13.381777",
        },
    )
    assert data["country"] == "DE"
    assert data["is_complete"] is True

    status_resp = await client.get(STATUS_URL, headers=headers)
    status_data = status_resp.json()["data"]
    assert status_data["service_location_completed_at"] is not None
    assert status_data["current_step"] == "AVAILABILITY"


async def test_salon_requires_salon_name(client: AsyncClient, db_session: AsyncSession):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}

    without_name = await _put(
        client,
        headers,
        {
            "location_type": "SALON",
            "address_line1": "Hauptstrasse 5",
            "city": "Munich",
            "postal_code": "80331",
            "country": "DE",
            "latitude": "48.135125",
            "longitude": "11.581981",
        },
    )
    assert without_name["is_complete"] is False

    with_name = await _put(client, headers, {"salon_name": "Glamour Braids Studio"})
    assert with_name["salon_name"] == "Glamour Braids Studio"
    assert with_name["is_complete"] is True


async def test_mobile_only_completion(client: AsyncClient, db_session: AsyncSession):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}

    data = await _put(
        client,
        headers,
        {
            "offers_mobile": True,
            "travel_radius_km": 15,
            "city": "Hamburg",
            "country": "DE",
            "latitude": "53.551086",
            "longitude": "9.993682",
        },
    )
    assert data["location_type"] is None
    assert data["is_complete"] is True


async def test_uncompletes_when_a_required_field_is_cleared(
    client: AsyncClient, db_session: AsyncSession
):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}

    await _put(
        client,
        headers,
        {
            "offers_mobile": True,
            "travel_radius_km": 15,
            "city": "Hamburg",
            "country": "DE",
            "latitude": "53.551086",
            "longitude": "9.993682",
        },
    )
    status_before = await client.get(STATUS_URL, headers=headers)
    assert status_before.json()["data"]["service_location_completed_at"] is not None

    cleared = await _put(client, headers, {"travel_radius_km": None})
    assert cleared["is_complete"] is False

    status_after = await client.get(STATUS_URL, headers=headers)
    assert status_after.json()["data"]["service_location_completed_at"] is None


async def test_switching_away_from_salon_clears_salon_name(
    client: AsyncClient, db_session: AsyncSession
):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}

    await _put(
        client,
        headers,
        {
            "location_type": "SALON",
            "salon_name": "Glamour Braids Studio",
            "address_line1": "Hauptstrasse 5",
            "city": "Munich",
            "postal_code": "80331",
            "country": "DE",
            "latitude": "48.135125",
            "longitude": "11.581981",
        },
    )

    switched = await _put(client, headers, {"location_type": "HOME_STUDIO"})
    assert switched["salon_name"] is None


async def test_turning_mobile_off_clears_radius_and_fee(
    client: AsyncClient, db_session: AsyncSession
):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}

    await _put(
        client,
        headers,
        {
            "offers_mobile": True,
            "travel_radius_km": 15,
            "travel_fee": "10.00",
            "city": "Hamburg",
            "country": "DE",
            "latitude": "53.551086",
            "longitude": "9.993682",
        },
    )

    turned_off = await _put(client, headers, {"offers_mobile": False})
    assert turned_off["travel_radius_km"] is None
    assert turned_off["travel_fee"] is None


async def test_invalid_country_code_rejected(client: AsyncClient, db_session: AsyncSession):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    resp = await client.put(
        LOCATION_URL,
        json={"country": "Germany"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422

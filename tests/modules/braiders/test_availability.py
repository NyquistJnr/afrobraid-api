from datetime import UTC, date, datetime, timedelta

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
SETTINGS_URL = "/api/v1/braiders/onboarding/availability/settings"
WINDOWS_URL = "/api/v1/braiders/onboarding/availability/weekly-windows"
EXCEPTIONS_URL = "/api/v1/braiders/onboarding/availability/exceptions"


def _next_weekday(target_weekday: int) -> date:
    """The next date (strictly in the future, at least a full week out) that
    falls on `target_weekday` (Monday=0) - keeps slot tests far enough ahead
    that the default 2-hour min-notice window never clips them."""
    today = date.today()
    days_ahead = (target_weekday - today.weekday()) % 7
    return today + timedelta(days=days_ahead + 7)


async def _published_style(client: AsyncClient, admin_headers: dict, *, name: str) -> str:
    style_resp = await client.post(STYLES_URL, json={"name": name}, headers=admin_headers)
    style = style_resp.json()["data"]
    await client.put(f"{STYLES_URL}/{style['id']}", json={"is_active": True}, headers=admin_headers)
    return style["id"]


async def _add_to_menu(
    client: AsyncClient, braider_headers: dict, style_id: str, *, duration_minutes: int | None
) -> str:
    payload = {"style_id": style_id, "base_price": "180.00"}
    if duration_minutes is not None:
        payload["duration_minutes"] = duration_minutes
    resp = await client.post(SERVICES_URL, json=payload, headers=braider_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _profile_id(db_session: AsyncSession, user_id) -> str:
    # The public slots endpoint is keyed on BraiderProfile.id, not User.id -
    # every onboarding call above creates the profile as a side effect.
    profile = await braiders_repo.get_profile_by_user_id(db_session, user_id)
    return str(profile.id)


async def test_settings_defaults_and_update(client: AsyncClient, db_session: AsyncSession):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}

    get_resp = await client.get(SETTINGS_URL, headers=headers)
    assert get_resp.status_code == 200
    defaults = get_resp.json()["data"]
    assert defaults["timezone"] == "UTC"
    assert defaults["min_notice_hours"] == 2
    assert defaults["max_advance_days"] == 60
    assert defaults["buffer_minutes"] == 0

    update_resp = await client.put(
        SETTINGS_URL,
        json={"timezone": "Africa/Lagos", "buffer_minutes": 15},
        headers=headers,
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()["data"]
    assert updated["timezone"] == "Africa/Lagos"
    assert updated["buffer_minutes"] == 15
    assert updated["min_notice_hours"] == 2


async def test_invalid_timezone_rejected(client: AsyncClient, db_session: AsyncSession):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    resp = await client.put(
        SETTINGS_URL,
        json={"timezone": "Mars/Olympus_Mons"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_TIMEZONE"


async def test_weekly_window_crud_and_overlap_rejection(
    client: AsyncClient, db_session: AsyncSession
):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        WINDOWS_URL,
        json={"day_of_week": "MONDAY", "start_time": "09:00", "end_time": "12:00"},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    window = create_resp.json()["data"]
    assert window["day_of_week"] == "MONDAY"
    assert window["is_active"] is True

    # A second, non-overlapping window the same day (split shift) is fine.
    second = await client.post(
        WINDOWS_URL,
        json={"day_of_week": "MONDAY", "start_time": "13:00", "end_time": "17:00"},
        headers=headers,
    )
    assert second.status_code == 201, second.text

    overlap_resp = await client.post(
        WINDOWS_URL,
        json={"day_of_week": "MONDAY", "start_time": "11:00", "end_time": "14:00"},
        headers=headers,
    )
    assert overlap_resp.status_code == 409
    assert overlap_resp.json()["error"]["code"] == "OVERLAPPING_AVAILABILITY_WINDOW"

    list_resp = await client.get(WINDOWS_URL, headers=headers)
    assert len(list_resp.json()["data"]) == 2

    patch_resp = await client.patch(
        f"{WINDOWS_URL}/{window['id']}", json={"is_active": False}, headers=headers
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["is_active"] is False

    delete_resp = await client.delete(f"{WINDOWS_URL}/{window['id']}", headers=headers)
    assert delete_resp.status_code == 204

    list_after = await client.get(WINDOWS_URL, headers=headers)
    assert len(list_after.json()["data"]) == 1


async def test_invalid_window_times_rejected(client: AsyncClient, db_session: AsyncSession):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    resp = await client.post(
        WINDOWS_URL,
        json={"day_of_week": "TUESDAY", "start_time": "17:00", "end_time": "09:00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_creating_first_window_completes_availability_step(
    client: AsyncClient, db_session: AsyncSession
):
    braider, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}

    onboarding_status = await braiders_repo.create_onboarding_status_for_user(
        db_session, braider.id
    )
    now = datetime.now(UTC)
    onboarding_status.business_info_completed_at = now
    onboarding_status.phone_verification_completed_at = now
    onboarding_status.veriff_completed_at = now
    onboarding_status.service_type_completed_at = now
    onboarding_status.portfolio_completed_at = now
    onboarding_status.service_location_completed_at = now
    onboarding_status.current_step = OnboardingStep.AVAILABILITY
    await db_session.commit()

    await client.post(
        WINDOWS_URL,
        json={"day_of_week": "WEDNESDAY", "start_time": "09:00", "end_time": "17:00"},
        headers=headers,
    )

    status_resp = await client.get(STATUS_URL, headers=headers)
    status_data = status_resp.json()["data"]
    assert status_data["availability_completed_at"] is not None
    assert status_data["current_step"] == "PAYMENT_SETUP"


async def test_exception_crud_closed_custom_hours_and_conflicts(
    client: AsyncClient, db_session: AsyncSession
):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}
    holiday = _next_weekday(4).isoformat()
    other_day = _next_weekday(2).isoformat()

    closed_resp = await client.post(
        EXCEPTIONS_URL,
        json={"date": holiday, "exception_type": "CLOSED", "reason": "Public holiday"},
        headers=headers,
    )
    assert closed_resp.status_code == 201, closed_resp.text
    closed = closed_resp.json()["data"]
    assert closed["start_time"] is None

    # Can't also add custom hours on a date that's already CLOSED.
    conflict_resp = await client.post(
        EXCEPTIONS_URL,
        json={
            "date": holiday,
            "exception_type": "CUSTOM_HOURS",
            "start_time": "09:00",
            "end_time": "12:00",
        },
        headers=headers,
    )
    assert conflict_resp.status_code == 409
    assert conflict_resp.json()["error"]["code"] == "OVERLAPPING_AVAILABILITY_EXCEPTION"

    custom_resp = await client.post(
        EXCEPTIONS_URL,
        json={
            "date": other_day,
            "exception_type": "CUSTOM_HOURS",
            "start_time": "09:00",
            "end_time": "12:00",
        },
        headers=headers,
    )
    assert custom_resp.status_code == 201, custom_resp.text

    overlapping_custom = await client.post(
        EXCEPTIONS_URL,
        json={
            "date": other_day,
            "exception_type": "CUSTOM_HOURS",
            "start_time": "11:00",
            "end_time": "14:00",
        },
        headers=headers,
    )
    assert overlapping_custom.status_code == 409

    list_resp = await client.get(EXCEPTIONS_URL, headers=headers)
    assert len(list_resp.json()["data"]) == 2

    delete_resp = await client.delete(f"{EXCEPTIONS_URL}/{closed['id']}", headers=headers)
    assert delete_resp.status_code == 204


async def test_exception_invalid_shapes_rejected(client: AsyncClient, db_session: AsyncSession):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}
    a_date = _next_weekday(1).isoformat()

    closed_with_times = await client.post(
        EXCEPTIONS_URL,
        json={
            "date": a_date,
            "exception_type": "CLOSED",
            "start_time": "09:00",
            "end_time": "12:00",
        },
        headers=headers,
    )
    assert closed_with_times.status_code == 422

    custom_without_times = await client.post(
        EXCEPTIONS_URL,
        json={"date": a_date, "exception_type": "CUSTOM_HOURS"},
        headers=headers,
    )
    assert custom_without_times.status_code == 422


async def test_compute_available_slots_from_weekly_pattern(
    client: AsyncClient, db_session: AsyncSession
):
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    style_id = await _published_style(client, admin_headers, name="Box Braids")

    braider, braider_token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    braider_headers = {"Authorization": f"Bearer {braider_token}"}
    braider_style_id = await _add_to_menu(
        client, braider_headers, style_id, duration_minutes=60
    )

    await client.put(SETTINGS_URL, json={"timezone": "Africa/Lagos"}, headers=braider_headers)
    monday = _next_weekday(0)
    await client.post(
        WINDOWS_URL,
        json={"day_of_week": "MONDAY", "start_time": "09:00", "end_time": "11:00"},
        headers=braider_headers,
    )

    slots_resp = await client.get(
        f"/api/v1/braiders/{await _profile_id(db_session, braider.id)}/availability/slots",
        params={
            "style_id": style_id,
            "date_from": monday.isoformat(),
            "date_to": monday.isoformat(),
        },
    )
    assert slots_resp.status_code == 200, slots_resp.text
    slots = slots_resp.json()["data"]
    assert len(slots) == 2
    # Africa/Lagos is UTC+1 with no DST, so 09:00 local -> 08:00 UTC.
    assert slots[0]["start_at"].startswith(f"{monday.isoformat()}T08:00")
    assert slots[1]["start_at"].startswith(f"{monday.isoformat()}T09:00")

    assert braider_style_id  # sanity: menu entry was created


async def test_closed_exception_removes_that_days_slots(
    client: AsyncClient, db_session: AsyncSession
):
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    style_id = await _published_style(client, admin_headers, name="Cornrows")

    braider, braider_token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    braider_headers = {"Authorization": f"Bearer {braider_token}"}
    await _add_to_menu(client, braider_headers, style_id, duration_minutes=30)
    await client.put(SETTINGS_URL, json={"timezone": "UTC"}, headers=braider_headers)

    monday = _next_weekday(0)
    await client.post(
        WINDOWS_URL,
        json={"day_of_week": "MONDAY", "start_time": "09:00", "end_time": "10:00"},
        headers=braider_headers,
    )
    await client.post(
        EXCEPTIONS_URL,
        json={"date": monday.isoformat(), "exception_type": "CLOSED"},
        headers=braider_headers,
    )

    slots_resp = await client.get(
        f"/api/v1/braiders/{await _profile_id(db_session, braider.id)}/availability/slots",
        params={
            "style_id": style_id,
            "date_from": monday.isoformat(),
            "date_to": monday.isoformat(),
        },
    )
    assert slots_resp.json()["data"] == []


async def test_custom_hours_exception_overrides_weekly_pattern(
    client: AsyncClient, db_session: AsyncSession
):
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    style_id = await _published_style(client, admin_headers, name="Fulani Braids")

    braider, braider_token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    braider_headers = {"Authorization": f"Bearer {braider_token}"}
    await _add_to_menu(client, braider_headers, style_id, duration_minutes=30)
    await client.put(SETTINGS_URL, json={"timezone": "UTC"}, headers=braider_headers)

    monday = _next_weekday(0)
    await client.post(
        WINDOWS_URL,
        json={"day_of_week": "MONDAY", "start_time": "09:00", "end_time": "10:00"},
        headers=braider_headers,
    )
    await client.post(
        EXCEPTIONS_URL,
        json={
            "date": monday.isoformat(),
            "exception_type": "CUSTOM_HOURS",
            "start_time": "14:00",
            "end_time": "14:30",
        },
        headers=braider_headers,
    )

    slots_resp = await client.get(
        f"/api/v1/braiders/{await _profile_id(db_session, braider.id)}/availability/slots",
        params={
            "style_id": style_id,
            "date_from": monday.isoformat(),
            "date_to": monday.isoformat(),
        },
    )
    slots = slots_resp.json()["data"]
    assert len(slots) == 1
    assert slots[0]["start_at"].startswith(f"{monday.isoformat()}T14:00")


async def test_slots_require_settings_configured(client: AsyncClient, db_session: AsyncSession):
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    style_id = await _published_style(client, admin_headers, name="Passion Twists")

    braider, braider_token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    braider_headers = {"Authorization": f"Bearer {braider_token}"}
    await _add_to_menu(client, braider_headers, style_id, duration_minutes=45)

    monday = _next_weekday(0)
    resp = await client.get(
        f"/api/v1/braiders/{await _profile_id(db_session, braider.id)}/availability/slots",
        params={
            "style_id": style_id,
            "date_from": monday.isoformat(),
            "date_to": monday.isoformat(),
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "AVAILABILITY_SETTINGS_NOT_CONFIGURED"


async def test_slots_require_style_duration(client: AsyncClient, db_session: AsyncSession):
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    style_id = await _published_style(client, admin_headers, name="Senegalese Twists")

    braider, braider_token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    braider_headers = {"Authorization": f"Bearer {braider_token}"}
    await _add_to_menu(client, braider_headers, style_id, duration_minutes=None)
    await client.put(SETTINGS_URL, json={"timezone": "UTC"}, headers=braider_headers)

    monday = _next_weekday(0)
    resp = await client.get(
        f"/api/v1/braiders/{await _profile_id(db_session, braider.id)}/availability/slots",
        params={
            "style_id": style_id,
            "date_from": monday.isoformat(),
            "date_to": monday.isoformat(),
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "BRAIDER_STYLE_DURATION_MISSING"

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.calculations import repository as calculations_repo
from app.modules.bookings.calculations.cron import expire_booking_calculations_cron
from app.modules.bookings.calculations.models import BookingCalculation, BookingCalculationStatus
from app.modules.styles.models import Style
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

CALC_URL = "/api/v1/booking-calculations"


async def test_create_calculation_basic(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session, base_price="180.00")

    resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]

    # subtotal 180 -> fee 10% = 18 -> vat_service 20% of 180 = 36 ->
    # vat_platform_fee 20% of 18 = 3.60 -> total 180+18+39.60 = 237.60 ->
    # deposit (indicative, 10% of total) = 23.76, balance = 213.84.
    assert data["status"] == "DRAFT"
    assert data["service_subtotal"] == "180.00"
    assert data["subtotal"] == "180.00"
    assert data["platform_fee"] == "18.00"
    assert data["vat_on_service"] == "36.00"
    assert data["vat_on_platform_fee"] == "3.60"
    assert data["vat_total"] == "39.60"
    assert data["total"] == "237.60"
    assert data["deposit_amount"] == "23.76"
    assert data["balance_amount"] == "213.84"
    assert data["is_mobile"] is False
    assert data["travel_fee"] == "0.00"
    item_types = [item["item_type"] for item in data["items"]]
    assert "SERVICE" in item_types
    assert "PLATFORM_FEE" in item_types
    assert "VAT_SERVICE" in item_types
    assert "VAT_PLATFORM_FEE" in item_types


async def test_create_calculation_with_variation_replaces_base_price(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(
        db_session, base_price="180.00", with_variation=True, variation_price="200.00"
    )

    resp = await client.post(
        CALC_URL,
        json={
            "braider_id": str(braider["braider_id"]),
            "style_id": str(braider["style_id"]),
            "braider_style_variation_id": str(braider["braider_style_variation_id"]),
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["service_subtotal"] == "200.00"
    assert data["subtotal"] == "200.00"
    variation_lines = [item for item in data["items"] if item["item_type"] == "VARIATION"]
    assert len(variation_lines) == 1
    assert variation_lines[0]["line_amount"] == "200.00"


async def test_create_calculation_required_addon_auto_included(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(
        db_session,
        base_price="100.00",
        with_addon=True,
        addon_price="10.00",
        addon_required=True,
    )

    # Not requesting the addon at all - it must still be included and priced in.
    resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["service_subtotal"] == "110.00"
    addon_lines = [item for item in data["items"] if item["item_type"] == "ADDON"]
    assert len(addon_lines) == 1
    assert addon_lines[0]["is_required"] is True


async def test_create_calculation_optional_addon_only_when_selected(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(
        db_session, base_price="100.00", with_addon=True, addon_price="15.00", addon_required=False
    )

    without = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    assert without.json()["data"]["service_subtotal"] == "100.00"

    with_addon = await client.post(
        CALC_URL,
        json={
            "braider_id": str(braider["braider_id"]),
            "style_id": str(braider["style_id"]),
            "braider_style_addon_ids": [str(braider["braider_style_addon_id"])],
        },
    )
    assert with_addon.json()["data"]["service_subtotal"] == "115.00"


async def test_create_calculation_addon_not_belonging_to_braider_rejected(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(db_session, base_price="100.00")

    resp = await client.post(
        CALC_URL,
        json={
            "braider_id": str(braider["braider_id"]),
            "style_id": str(braider["style_id"]),
            "braider_style_addon_ids": [str(uuid.uuid4())],
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_ADDON"


async def test_create_calculation_variation_not_belonging_to_braider_rejected(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(db_session, base_price="100.00")

    resp = await client.post(
        CALC_URL,
        json={
            "braider_id": str(braider["braider_id"]),
            "style_id": str(braider["style_id"]),
            "braider_style_variation_id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_STYLE_VARIATION"


async def test_create_calculation_mobile_without_support_rejected(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(db_session, base_price="100.00", offers_mobile=False)

    resp = await client.post(
        CALC_URL,
        json={
            "braider_id": str(braider["braider_id"]),
            "style_id": str(braider["style_id"]),
            "is_mobile": True,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "MOBILE_SERVICE_NOT_OFFERED"


async def test_create_calculation_mobile_adds_travel_fee(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(
        db_session, base_price="100.00", offers_mobile=True, travel_fee="12.50"
    )

    resp = await client.post(
        CALC_URL,
        json={
            "braider_id": str(braider["braider_id"]),
            "style_id": str(braider["style_id"]),
            "is_mobile": True,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["travel_fee"] == "12.50"
    assert data["subtotal"] == "112.50"


async def test_create_calculation_null_travel_fee_is_free(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(
        db_session, base_price="100.00", offers_mobile=True, travel_fee=None
    )

    resp = await client.post(
        CALC_URL,
        json={
            "braider_id": str(braider["braider_id"]),
            "style_id": str(braider["style_id"]),
            "is_mobile": True,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["travel_fee"] == "0.00"
    assert not any(item["item_type"] == "TRAVEL" for item in data["items"])


async def test_create_calculation_unknown_braider_404(client: AsyncClient, db_session: AsyncSession):
    resp = await client.post(
        CALC_URL, json={"braider_id": str(uuid.uuid4()), "style_id": str(uuid.uuid4())}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "BRAIDER_NOT_FOUND"


async def test_create_calculation_style_not_offered_404(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(db_session)
    resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(uuid.uuid4())}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "BRAIDER_STYLE_NOT_FOUND"


async def test_preview_does_not_persist(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session, base_price="150.00")

    resp = await client.post(
        f"{CALC_URL}/preview",
        json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "id" not in data
    assert data["total"] is not None

    result = await db_session.execute(select(BookingCalculation))
    assert result.scalars().all() == []


async def test_get_calculation_returns_created(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session, base_price="150.00")
    create_resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    calculation_id = create_resp.json()["data"]["id"]

    get_resp = await client.get(f"{CALC_URL}/{calculation_id}")
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["data"]["id"] == calculation_id
    assert get_resp.json()["data"]["total"] == create_resp.json()["data"]["total"]


async def test_get_unknown_calculation_404(client: AsyncClient, db_session: AsyncSession):
    resp = await client.get(f"{CALC_URL}/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "BOOKING_CALCULATION_NOT_FOUND"


async def test_patch_recomputes_when_mobile_toggled(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(
        db_session, base_price="100.00", offers_mobile=True, travel_fee="20.00"
    )
    create_resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    calculation_id = create_resp.json()["data"]["id"]
    assert create_resp.json()["data"]["subtotal"] == "100.00"

    patch_resp = await client.patch(f"{CALC_URL}/{calculation_id}", json={"is_mobile": True})
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["data"]["subtotal"] == "120.00"
    assert patch_resp.json()["data"]["travel_fee"] == "20.00"


async def test_patch_replaces_addons_when_field_included(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(
        db_session, base_price="100.00", with_addon=True, addon_price="10.00"
    )
    create_resp = await client.post(
        CALC_URL,
        json={
            "braider_id": str(braider["braider_id"]),
            "style_id": str(braider["style_id"]),
            "braider_style_addon_ids": [str(braider["braider_style_addon_id"])],
        },
    )
    calculation_id = create_resp.json()["data"]["id"]
    assert create_resp.json()["data"]["service_subtotal"] == "110.00"

    patch_resp = await client.patch(
        f"{CALC_URL}/{calculation_id}", json={"braider_style_addon_ids": []}
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["data"]["service_subtotal"] == "100.00"


async def test_patch_keeps_addons_when_field_omitted(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(
        db_session, base_price="100.00", with_addon=True, addon_price="10.00"
    )
    create_resp = await client.post(
        CALC_URL,
        json={
            "braider_id": str(braider["braider_id"]),
            "style_id": str(braider["style_id"]),
            "braider_style_addon_ids": [str(braider["braider_style_addon_id"])],
        },
    )
    calculation_id = create_resp.json()["data"]["id"]

    # is_mobile isn't offered, so patching something unrelated must not drop
    # the previously-selected addon.
    patch_resp = await client.patch(f"{CALC_URL}/{calculation_id}", json={})
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["data"]["service_subtotal"] == "110.00"


async def test_patch_rejected_when_consumed(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session)
    create_resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    calculation_id = create_resp.json()["data"]["id"]

    calculation = await calculations_repo.get_calculation_by_id(db_session, uuid.UUID(calculation_id))
    calculation.status = BookingCalculationStatus.CONSUMED
    await db_session.commit()

    patch_resp = await client.patch(f"{CALC_URL}/{calculation_id}", json={"is_mobile": False})
    assert patch_resp.status_code == 409
    assert patch_resp.json()["error"]["code"] == "BOOKING_CALCULATION_ALREADY_USED"

    delete_resp = await client.delete(f"{CALC_URL}/{calculation_id}")
    assert delete_resp.status_code == 409
    assert delete_resp.json()["error"]["code"] == "BOOKING_CALCULATION_ALREADY_USED"


async def test_patch_rejected_when_expired(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session)
    create_resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    calculation_id = create_resp.json()["data"]["id"]

    calculation = await calculations_repo.get_calculation_by_id(db_session, uuid.UUID(calculation_id))
    calculation.expires_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.commit()

    patch_resp = await client.patch(f"{CALC_URL}/{calculation_id}", json={"is_mobile": False})
    assert patch_resp.status_code == 409
    assert patch_resp.json()["error"]["code"] == "BOOKING_CALCULATION_EXPIRED"


async def test_delete_removes_draft(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session)
    create_resp = await client.post(
        CALC_URL, json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}
    )
    calculation_id = create_resp.json()["data"]["id"]

    delete_resp = await client.delete(f"{CALC_URL}/{calculation_id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"{CALC_URL}/{calculation_id}")
    assert get_resp.status_code == 404


async def test_locale_returns_translated_style_name(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session, base_price="100.00")
    style = await db_session.get(Style, braider["style_id"])
    style.name_de = "Rasterzöpfe"
    await db_session.commit()

    resp = await client.post(
        f"{CALC_URL}/preview?lang=de",
        json={"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["style_name"] == "Rasterzöpfe"


async def test_rate_limit_returns_429(client: AsyncClient, db_session: AsyncSession):
    braider = await create_bookable_braider(db_session, base_price="100.00")
    payload = {"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}

    last_status = None
    for _ in range(31):
        resp = await client.post(f"{CALC_URL}/preview", json=payload)
        last_status = resp.status_code

    assert last_status == 429
    assert resp.json()["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in resp.headers


async def test_cleanup_cron_deletes_only_expired_drafts(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(db_session, base_price="100.00")
    payload = {"braider_id": str(braider["braider_id"]), "style_id": str(braider["style_id"])}

    fresh_resp = await client.post(CALC_URL, json=payload)
    fresh_id = uuid.UUID(fresh_resp.json()["data"]["id"])

    expired_resp = await client.post(CALC_URL, json=payload)
    expired_id = uuid.UUID(expired_resp.json()["data"]["id"])
    expired_row = await calculations_repo.get_calculation_by_id(db_session, expired_id)
    expired_row.expires_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.commit()

    await expire_booking_calculations_cron({})

    # The cron ran in its own session/connection - expire this session's
    # identity map so the re-fetch below hits the DB instead of returning
    # the row it already cached from the .get() call above.
    db_session.expire_all()

    remaining = await calculations_repo.get_calculation_by_id(db_session, fresh_id)
    assert remaining is not None
    gone = await calculations_repo.get_calculation_by_id(db_session, expired_id)
    assert gone is None

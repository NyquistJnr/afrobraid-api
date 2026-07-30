import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.modules.styles.tasks import TASK_TRANSLATE_STYLE_TEXT
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token

pytestmark = pytest.mark.asyncio

CATEGORIES_URL = "/api/v1/admin/style-categories"
STYLES_URL = "/api/v1/admin/styles"


async def _admin_headers(db_session: AsyncSession) -> dict:
    _, token = await create_user_with_token(db_session, user_type=UserType.ADMIN)
    return {"Authorization": f"Bearer {token}"}


async def test_admin_creates_category_style_variation_and_addon(
    client: AsyncClient, db_session: AsyncSession, fake_queue
):
    headers = await _admin_headers(db_session)

    category_resp = await client.post(
        CATEGORIES_URL, json={"name": "Knotless Braids", "display_order": 1}, headers=headers
    )
    assert category_resp.status_code == 201, category_resp.text
    category = category_resp.json()["data"]
    assert category["slug"] == "knotless-braids"
    assert category["name_en"] == "Knotless Braids"
    assert category["name_en_source"] == "HUMAN"

    style_resp = await client.post(
        STYLES_URL,
        json={
            "category_id": category["id"],
            "name": "Knotless Braids - Mid Back",
            "description": "Classic knotless braids finished at mid-back length.",
        },
        headers=headers,
    )
    assert style_resp.status_code == 201, style_resp.text
    style = style_resp.json()["data"]
    assert style["is_active"] is False
    assert style["category_id"] == category["id"]

    # Creating with a name (and description) triggers one translation job per
    # field - both share TASK_TRANSLATE_STYLE_TEXT, so find each by "field".
    translate_jobs = {
        kwargs["field"]: kwargs
        for name, kwargs in fake_queue.jobs
        if name == TASK_TRANSLATE_STYLE_TEXT
    }
    assert translate_jobs["name"]["entity_type"] == "style"
    assert set(translate_jobs["name"]["target_locales"]) == {"de", "fr"}
    assert translate_jobs["description"]["entity_type"] == "style"
    assert set(translate_jobs["description"]["target_locales"]) == {"de", "fr"}

    variation_resp = await client.post(
        f"{STYLES_URL}/{style['id']}/variations",
        json={"name": "Mid-back length", "display_order": 1},
        headers=headers,
    )
    assert variation_resp.status_code == 201, variation_resp.text
    assert variation_resp.json()["data"]["name_en"] == "Mid-back length"

    addon_resp = await client.post(
        "/api/v1/admin/addons",
        json={"name": "Beads", "suggested_price": "15.00"},
        headers=headers,
    )
    assert addon_resp.status_code == 201, addon_resp.text
    assert addon_resp.json()["data"]["suggested_price"] == "15.00"

    publish_resp = await client.put(
        f"{STYLES_URL}/{style['id']}", json={"is_active": True}, headers=headers
    )
    assert publish_resp.status_code == 200
    assert publish_resp.json()["data"]["is_active"] is True


async def test_style_image_upload_enforces_max_six(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    headers = await _admin_headers(db_session)

    style_resp = await client.post(STYLES_URL, json={"name": "Cornrows"}, headers=headers)
    style_id = style_resp.json()["data"]["id"]

    monkeypatch.setattr(storage, "generate_presigned_upload_url", lambda *a, **k: "https://upload.example/put")
    monkeypatch.setattr(
        storage, "head_object", lambda key: storage.ObjectMetadata(content_length=1024, content_type="image/jpeg")
    )
    monkeypatch.setattr(storage, "delete_object", lambda key: None)

    for _ in range(6):
        upload_url_resp = await client.post(
            f"{STYLES_URL}/{style_id}/images/upload-url",
            json={"content_type": "image/jpeg"},
            headers=headers,
        )
        assert upload_url_resp.status_code == 200, upload_url_resp.text
        object_key = upload_url_resp.json()["data"]["object_key"]

        confirm_resp = await client.post(
            f"{STYLES_URL}/{style_id}/images/confirm", json={"object_key": object_key}, headers=headers
        )
        assert confirm_resp.status_code == 201, confirm_resp.text

    seventh_resp = await client.post(
        f"{STYLES_URL}/{style_id}/images/upload-url",
        json={"content_type": "image/jpeg"},
        headers=headers,
    )
    assert seventh_resp.status_code == 400
    assert seventh_resp.json()["error"]["code"] == "MAX_STYLE_IMAGES_REACHED"


async def test_braider_cannot_access_admin_style_routes(client: AsyncClient, db_session: AsyncSession):
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    resp = await client.post(
        STYLES_URL, json={"name": "Cornrows"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_braider_can_browse_published_styles(client: AsyncClient, db_session: AsyncSession):
    admin_headers = await _admin_headers(db_session)
    style_resp = await client.post(STYLES_URL, json={"name": "Passion Twists"}, headers=admin_headers)
    style_id = style_resp.json()["data"]["id"]
    await client.put(f"{STYLES_URL}/{style_id}", json={"is_active": True}, headers=admin_headers)

    _, braider_token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    braider_headers = {"Authorization": f"Bearer {braider_token}"}

    list_resp = await client.get("/api/v1/styles", headers=braider_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]["items"]
    assert any(item["id"] == style_id for item in items)

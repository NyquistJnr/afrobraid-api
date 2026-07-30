import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.modules.braiders import repository as braiders_repo
from app.modules.braiders.models import OnboardingStep
from app.modules.braiders.portfolio.tasks import TASK_TRANSLATE_PORTFOLIO_CAPTION
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token

pytestmark = pytest.mark.asyncio

PORTFOLIO_URL = "/api/v1/braiders/onboarding/portfolio"
STATUS_URL = "/api/v1/braiders/onboarding/status"


def _mock_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        storage, "generate_presigned_upload_url", lambda *a, **k: "https://upload.example/put"
    )
    monkeypatch.setattr(
        storage,
        "head_object",
        lambda key: storage.ObjectMetadata(content_length=1024, content_type="image/jpeg"),
    )
    monkeypatch.setattr(storage, "delete_object", lambda key: None)


async def _upload_photo(client: AsyncClient, headers: dict, caption: str | None = None) -> dict:
    upload_url_resp = await client.post(
        f"{PORTFOLIO_URL}/upload-url", json={"content_type": "image/jpeg"}, headers=headers
    )
    assert upload_url_resp.status_code == 200, upload_url_resp.text
    object_key = upload_url_resp.json()["data"]["object_key"]

    confirm_resp = await client.post(
        f"{PORTFOLIO_URL}/confirm",
        json={"object_key": object_key, "caption": caption},
        headers=headers,
    )
    assert confirm_resp.status_code == 201, confirm_resp.text
    return confirm_resp.json()["data"]


async def test_uploading_enough_photos_completes_the_step(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)

    braider, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}

    # Realistically the braider reaches PORTFOLIO only after SERVICE_TYPE.
    onboarding_status = await braiders_repo.create_onboarding_status_for_user(db_session, braider.id)
    onboarding_status.current_step = OnboardingStep.PORTFOLIO
    await db_session.commit()

    await _upload_photo(client, headers, caption="Knotless braids")
    await _upload_photo(client, headers)

    mid_status = await client.get(STATUS_URL, headers=headers)
    assert mid_status.json()["data"]["portfolio_completed_at"] is None
    assert mid_status.json()["data"]["current_step"] == "PORTFOLIO"

    third = await _upload_photo(client, headers, caption="Box braids, medium")
    assert third["caption_en"] == "Box braids, medium"
    assert third["caption_en_source"] == "HUMAN"
    assert third["caption_de_source"] == "PENDING"
    assert third["caption_fr_source"] == "PENDING"
    assert third["position"] == 2

    final_status = await client.get(STATUS_URL, headers=headers)
    assert final_status.json()["data"]["portfolio_completed_at"] is not None
    assert final_status.json()["data"]["current_step"] == "SERVICE_LOCATION"

    portfolio = await client.get(PORTFOLIO_URL, headers=headers)
    portfolio_data = portfolio.json()["data"]
    assert portfolio_data["is_complete"] is True
    assert portfolio_data["min_required"] == 3
    assert len(portfolio_data["images"]) == 3


async def test_update_caption_and_delete(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}

    image = await _upload_photo(client, headers)

    update_resp = await client.put(
        f"{PORTFOLIO_URL}/{image['id']}", json={"caption": "New caption"}, headers=headers
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()["data"]
    assert updated["caption_en"] == "New caption"
    assert updated["caption_en_source"] == "HUMAN"

    clear_resp = await client.put(
        f"{PORTFOLIO_URL}/{image['id']}", json={"caption": None}, headers=headers
    )
    assert clear_resp.status_code == 200
    cleared = clear_resp.json()["data"]
    assert cleared["caption_en"] is None
    assert cleared["caption_de"] is None
    assert cleared["caption_fr"] is None

    delete_resp = await client.delete(f"{PORTFOLIO_URL}/{image['id']}", headers=headers)
    assert delete_resp.status_code == 204

    portfolio = await client.get(PORTFOLIO_URL, headers=headers)
    assert portfolio.json()["data"]["images"] == []


async def test_caption_translation_is_enqueued(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, fake_queue
):
    _mock_storage(monkeypatch)
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}

    await _upload_photo(client, headers, caption="Knotless braids, waist length")

    job = fake_queue.last_job_kwargs(TASK_TRANSLATE_PORTFOLIO_CAPTION)
    assert job["source_locale"] == "en"
    assert job["source_text"] == "Knotless braids, waist length"
    assert set(job["target_locales"]) == {"de", "fr"}


async def test_max_photos_enforced(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(20):
        await _upload_photo(client, headers)

    resp = await client.post(
        f"{PORTFOLIO_URL}/upload-url", json={"content_type": "image/jpeg"}, headers=headers
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MAX_PORTFOLIO_IMAGES_REACHED"


async def test_cannot_confirm_upload_with_another_users_object_key(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)
    _, token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        f"{PORTFOLIO_URL}/confirm",
        json={"object_key": "braiders/00000000-0000-0000-0000-000000000000/portfolio/x.jpg"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_PORTFOLIO_IMAGE_UPLOAD"


async def test_scoped_to_owning_braider(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)
    _, owner_token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    image = await _upload_photo(client, {"Authorization": f"Bearer {owner_token}"})

    _, other_token = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    update_resp = await client.put(
        f"{PORTFOLIO_URL}/{image['id']}", json={"caption": "hijacked"}, headers=other_headers
    )
    assert update_resp.status_code == 404
    assert update_resp.json()["error"]["code"] == "PORTFOLIO_IMAGE_NOT_FOUND"

    delete_resp = await client.delete(f"{PORTFOLIO_URL}/{image['id']}", headers=other_headers)
    assert delete_resp.status_code == 404

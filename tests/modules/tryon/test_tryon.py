import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.config import get_settings
from app.modules.styles.models import Style, StyleVariation
from app.modules.tryon import tasks as tryon_tasks
from app.modules.tryon.models import TryOnFailureReason, TryOnStatus
from app.modules.tryon.repository import get_tryon_by_id
from app.modules.tryon.tasks import TASK_GENERATE_HAIRSTYLE_TRYON
from app.modules.users.models import UserType
from tests.helpers import create_user_with_token

pytestmark = pytest.mark.asyncio

TRYON_URL = "/api/v1/tryon"
settings = get_settings()


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


async def _get_upload_object_key(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        f"{TRYON_URL}/upload-url", json={"content_type": "image/jpeg"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["object_key"]


async def _create_tryon(client: AsyncClient, headers: dict, **extra) -> dict:
    object_key = await _get_upload_object_key(client, headers)
    resp = await client.post(
        TRYON_URL, json={"object_key": object_key, **extra}, headers=headers
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["data"]


async def _create_active_style(
    db_session: AsyncSession, *, name: str = "Box Braids", slug: str = "box-braids"
) -> Style:
    style = Style(slug=slug, name_en=name, is_active=True)
    db_session.add(style)
    await db_session.commit()
    await db_session.refresh(style)
    return style


async def test_upload_url_is_scoped_to_the_user(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)
    user, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    object_key = await _get_upload_object_key(client, headers)
    assert object_key.startswith(f"tryon/{user.id}/original/")


async def test_create_requires_style_or_description(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    object_key = await _get_upload_object_key(client, headers)
    resp = await client.post(TRYON_URL, json={"object_key": object_key}, headers=headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "TRYON_STYLE_OR_DESCRIPTION_REQUIRED"


async def test_create_with_description_only_enqueues_generation(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, fake_queue
):
    _mock_storage(monkeypatch)
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    tryon = await _create_tryon(
        client, headers, description="shoulder length, honey blonde highlights"
    )
    assert tryon["status"] == "PROCESSING"
    assert tryon["style"] is None
    assert tryon["description"] == "shoulder length, honey blonde highlights"

    job = fake_queue.last_job_kwargs(TASK_GENERATE_HAIRSTYLE_TRYON)
    assert job["tryon_id"] == tryon["id"]


async def test_create_with_style_includes_style_summary(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)
    style = await _create_active_style(db_session)
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    tryon = await _create_tryon(client, headers, style_id=str(style.id))
    assert tryon["style"]["id"] == str(style.id)
    assert tryon["style"]["name"] == "Box Braids"


async def test_style_variation_must_belong_to_style(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)
    style_a = await _create_active_style(db_session, name="Box Braids", slug="box-braids")
    style_b = await _create_active_style(db_session, name="Cornrows", slug="cornrows")
    variation_of_b = StyleVariation(style_id=style_b.id, name_en="Medium")
    db_session.add(variation_of_b)
    await db_session.commit()
    await db_session.refresh(variation_of_b)

    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}
    object_key = await _get_upload_object_key(client, headers)

    resp = await client.post(
        TRYON_URL,
        json={
            "object_key": object_key,
            "style_id": str(style_a.id),
            "style_variation_id": str(variation_of_b.id),
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "TRYON_STYLE_VARIATION_INVALID"


async def test_invalid_image_upload_rejected(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        storage, "generate_presigned_upload_url", lambda *a, **k: "https://upload.example/put"
    )
    monkeypatch.setattr(
        storage,
        "head_object",
        lambda key: storage.ObjectMetadata(content_length=99_999_999, content_type="image/jpeg"),
    )
    deleted: list[str] = []
    monkeypatch.setattr(storage, "delete_object", lambda key: deleted.append(key))

    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}
    object_key = await _get_upload_object_key(client, headers)

    resp = await client.post(
        TRYON_URL,
        json={"object_key": object_key, "description": "afro"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_TRYON_IMAGE_UPLOAD"
    assert deleted == [object_key]


async def test_cannot_create_with_another_users_object_key(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        TRYON_URL,
        json={
            "object_key": "tryon/00000000-0000-0000-0000-000000000000/original/x.jpg",
            "description": "afro",
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_TRYON_IMAGE_UPLOAD"


async def test_max_pending_tryons_enforced(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(settings.tryon_max_pending_per_user):
        await _create_tryon(client, headers, description="afro")

    object_key = await _get_upload_object_key(client, headers)
    resp = await client.post(
        TRYON_URL, json={"object_key": object_key, "description": "afro"}, headers=headers
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MAX_PENDING_TRYONS_REACHED"


async def test_get_list_and_delete(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)
    deleted: list[str] = []
    monkeypatch.setattr(storage, "delete_object", lambda key: deleted.append(key))
    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}

    tryon = await _create_tryon(client, headers, description="afro")
    assert tryon["original_url"] is not None

    get_resp = await client.get(f"{TRYON_URL}/{tryon['id']}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["id"] == tryon["id"]

    list_resp = await client.get(TRYON_URL, headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]) == 1

    delete_resp = await client.delete(f"{TRYON_URL}/{tryon['id']}", headers=headers)
    assert delete_resp.status_code == 204
    # Explicit deletion is the only time the original is removed from storage.
    assert len(deleted) == 1

    list_after = await client.get(TRYON_URL, headers=headers)
    assert list_after.json()["data"] == []


async def test_scoped_to_owning_user(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)
    _, owner_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    tryon = await _create_tryon(
        client, {"Authorization": f"Bearer {owner_token}"}, description="afro"
    )

    _, other_token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    get_resp = await client.get(f"{TRYON_URL}/{tryon['id']}", headers=other_headers)
    assert get_resp.status_code == 404
    assert get_resp.json()["error"]["code"] == "TRYON_NOT_FOUND"

    delete_resp = await client.delete(f"{TRYON_URL}/{tryon['id']}", headers=other_headers)
    assert delete_resp.status_code == 404


async def test_generation_task_success_keeps_both_photos_for_before_after(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)
    monkeypatch.setattr(storage, "get_object", lambda key: b"fake-original-bytes")
    put_calls: list[tuple[str, bytes, str]] = []
    monkeypatch.setattr(
        storage,
        "put_object",
        lambda key, data, *, content_type: put_calls.append((key, data, content_type)),
    )
    deleted: list[str] = []
    monkeypatch.setattr(storage, "delete_object", lambda key: deleted.append(key))

    async def fake_generate(image_bytes: bytes, *, instruction: str) -> bytes:
        assert image_bytes == b"fake-original-bytes"
        assert "afro" in instruction
        return b"fake-result-bytes"

    monkeypatch.setattr(tryon_tasks, "generate_hairstyle_image", fake_generate)

    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}
    tryon = await _create_tryon(client, headers, description="afro")
    assert tryon["original_url"] is not None
    source_key = (await get_tryon_by_id(db_session, uuid.UUID(tryon["id"]))).source_object_key

    await tryon_tasks.generate_hairstyle_tryon_task({}, tryon_id=tryon["id"])

    updated = await get_tryon_by_id(db_session, uuid.UUID(tryon["id"]))
    assert updated.status == TryOnStatus.COMPLETED
    # Both photos are kept for a before/after view - neither is deleted
    # automatically, only when the try-on itself is deleted.
    assert updated.source_object_key == source_key
    assert updated.result_object_key is not None
    assert put_calls[0][0] == updated.result_object_key
    assert deleted == []

    get_resp = await client.get(f"{TRYON_URL}/{tryon['id']}", headers=headers)
    body = get_resp.json()["data"]
    assert body["original_url"] is not None
    assert body["result_url"] is not None


async def test_generation_task_failure_marks_failed_and_keeps_original(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)
    monkeypatch.setattr(storage, "get_object", lambda key: b"fake-original-bytes")

    async def failing_generate(image_bytes: bytes, *, instruction: str) -> bytes:
        raise tryon_tasks.HuggingFaceApiError("model unavailable")

    monkeypatch.setattr(tryon_tasks, "generate_hairstyle_image", failing_generate)

    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}
    tryon = await _create_tryon(client, headers, description="afro")

    await tryon_tasks.generate_hairstyle_tryon_task({}, tryon_id=tryon["id"])

    updated = await get_tryon_by_id(db_session, uuid.UUID(tryon["id"]))
    assert updated.status == TryOnStatus.FAILED
    assert updated.failure_reason == TryOnFailureReason.GENERATION_FAILED
    assert updated.source_object_key is not None
    assert updated.result_object_key is None

    get_resp = await client.get(f"{TRYON_URL}/{tryon['id']}", headers=headers)
    body = get_resp.json()["data"]
    assert body["status"] == "FAILED"
    assert body["failure_reason"] == "GENERATION_FAILED"
    assert body["error_message"]


async def test_generation_task_ai_credit_exhausted_returns_friendly_reason(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    _mock_storage(monkeypatch)
    monkeypatch.setattr(storage, "get_object", lambda key: b"fake-original-bytes")

    async def failing_generate(image_bytes: bytes, *, instruction: str) -> bytes:
        raise tryon_tasks.HuggingFaceCreditExhaustedError("credits finished")

    monkeypatch.setattr(tryon_tasks, "generate_hairstyle_image", failing_generate)

    _, token = await create_user_with_token(db_session, user_type=UserType.CUSTOMER)
    headers = {"Authorization": f"Bearer {token}"}
    tryon = await _create_tryon(client, headers, description="afro")

    await tryon_tasks.generate_hairstyle_tryon_task({}, tryon_id=tryon["id"])

    updated = await get_tryon_by_id(db_session, uuid.UUID(tryon["id"]))
    assert updated.status == TryOnStatus.FAILED
    assert updated.failure_reason == TryOnFailureReason.AI_CREDIT_EXHAUSTED
    assert updated.source_object_key is not None
    assert updated.result_object_key is None

    get_resp = await client.get(f"{TRYON_URL}/{tryon['id']}", headers=headers)
    body = get_resp.json()["data"]
    assert body["status"] == "FAILED"
    assert body["failure_reason"] == "AI_CREDIT_EXHAUSTED"
    assert body["error_message"] == "The AI credit has finished for now. Please try again later."

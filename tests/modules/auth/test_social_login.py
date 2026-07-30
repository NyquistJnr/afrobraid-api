import pytest
from httpx import AsyncClient

from app.modules.auth import social as auth_social
from app.modules.auth.social.base import SocialProfile
from app.modules.users.models import AuthProvider
from tests.modules.auth.helpers import signup_and_verify

pytestmark = pytest.mark.asyncio

SOCIAL_URL = "/api/v1/auth/social/google"


def _patch_google(monkeypatch: pytest.MonkeyPatch, profile: SocialProfile) -> None:
    async def fake_verify(token: str) -> SocialProfile:
        return profile

    monkeypatch.setitem(auth_social._VERIFIERS, AuthProvider.GOOGLE, fake_verify)


def _profile(**overrides) -> SocialProfile:
    defaults = dict(
        provider_user_id="google-sub-1",
        email="ada@example.com",
        first_name="Ada",
        last_name="Lovelace",
        email_verified=True,
    )
    defaults.update(overrides)
    return SocialProfile(**defaults)


async def test_social_login_new_user_requires_user_type(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _patch_google(monkeypatch, _profile())

    resp = await client.post(SOCIAL_URL, json={"provider_token": "fake-token"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "USER_TYPE_REQUIRED"


async def test_social_login_new_user_success(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _patch_google(monkeypatch, _profile())

    resp = await client.post(
        SOCIAL_URL, json={"provider_token": "fake-token", "user_type": "CUSTOMER"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "ada@example.com"
    assert body["user_type"] == "CUSTOMER"
    assert "access_token" in body


async def test_social_login_existing_identity_logs_into_same_user(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _patch_google(monkeypatch, _profile())

    first = await client.post(
        SOCIAL_URL, json={"provider_token": "fake-token", "user_type": "CUSTOMER"}
    )
    second = await client.post(SOCIAL_URL, json={"provider_token": "fake-token"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


async def test_social_login_links_existing_email_account(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, fake_queue
):
    existing = await signup_and_verify(client, fake_queue, email="ada@example.com")

    _patch_google(monkeypatch, _profile())

    resp = await client.post(SOCIAL_URL, json={"provider_token": "fake-token"})
    assert resp.status_code == 200
    assert resp.json()["id"] == existing["id"]

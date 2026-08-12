import uuid
from types import SimpleNamespace

import pytest

from app.core.security import create_access_token
from app.modules.realtime import router as realtime_router

pytestmark = pytest.mark.asyncio


async def test_websocket_authentication_uses_short_lived_db_session(monkeypatch):
    events: list[str] = []
    user_id = uuid.uuid4()
    token, _ = create_access_token(user_id=user_id, user_type="CUSTOMER")
    session = object()

    class FakeSessionManager:
        async def __aenter__(self):
            events.append("enter")
            return session

        async def __aexit__(self, exc_type, exc, tb):
            events.append("exit")

    def fake_session_factory():
        events.append("factory")
        return FakeSessionManager()

    async def fake_get_user_by_id(db, requested_user_id):
        events.append("lookup")
        assert db is session
        assert requested_user_id == user_id
        return SimpleNamespace(is_active=True)

    monkeypatch.setattr(realtime_router, "AsyncSessionLocal", fake_session_factory)
    monkeypatch.setattr(realtime_router, "get_user_by_id", fake_get_user_by_id)

    authenticated_user_id = await realtime_router._authenticate_websocket_token(token)

    assert authenticated_user_id == user_id
    assert events == ["factory", "enter", "lookup", "exit"]


async def test_websocket_authentication_rejects_inactive_user(monkeypatch):
    user_id = uuid.uuid4()
    token, _ = create_access_token(user_id=user_id, user_type="CUSTOMER")

    class FakeSessionManager:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            pass

    async def fake_get_user_by_id(db, requested_user_id):
        return SimpleNamespace(is_active=False)

    monkeypatch.setattr(realtime_router, "AsyncSessionLocal", lambda: FakeSessionManager())
    monkeypatch.setattr(realtime_router, "get_user_by_id", fake_get_user_by_id)

    assert await realtime_router._authenticate_websocket_token(token) is None

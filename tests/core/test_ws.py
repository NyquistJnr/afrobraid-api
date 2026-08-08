import asyncio
import contextlib
import uuid

import pytest

from app.core import ws
from app.core.redis import get_redis_client

pytestmark = pytest.mark.asyncio


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


async def test_connection_manager_delivers_only_to_connected_user():
    manager = ws.ConnectionManager()
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    socket = _FakeWebSocket()
    other_socket = _FakeWebSocket()

    manager.connect(user_id, socket)
    manager.connect(other_user_id, other_socket)

    await manager.send_to_user(user_id, {"type": "ping"})
    assert socket.sent == [{"type": "ping"}]
    assert other_socket.sent == []


async def test_connection_manager_stops_delivering_after_disconnect():
    manager = ws.ConnectionManager()
    user_id = uuid.uuid4()
    socket = _FakeWebSocket()

    manager.connect(user_id, socket)
    manager.disconnect(user_id, socket)

    await manager.send_to_user(user_id, {"type": "ping"})
    assert socket.sent == []


async def test_connection_manager_fans_out_to_multiple_connections_for_same_user():
    manager = ws.ConnectionManager()
    user_id = uuid.uuid4()
    socket_a = _FakeWebSocket()
    socket_b = _FakeWebSocket()

    manager.connect(user_id, socket_a)
    manager.connect(user_id, socket_b)

    await manager.send_to_user(user_id, {"type": "ping"})
    assert socket_a.sent == [{"type": "ping"}]
    assert socket_b.sent == [{"type": "ping"}]


async def test_publish_event_reaches_locally_connected_socket_via_redis(monkeypatch):
    """End-to-end through the real Redis pub/sub bridge: publish_event()
    (what chat/notifications call) -> redis_listener() (what app.main's
    lifespan runs) -> the process-local ConnectionManager -> the socket."""
    user_id = uuid.uuid4()
    socket = _FakeWebSocket()
    monkeypatch.setattr(ws, "manager", ws.ConnectionManager())
    ws.manager.connect(user_id, socket)

    listener_client = get_redis_client()
    listener_task = asyncio.create_task(ws.redis_listener(listener_client))
    try:
        # Give the psubscribe a moment to actually register before publishing.
        await asyncio.sleep(0.2)
        await ws.publish_event(user_id, {"type": "notification", "hello": "world"})

        for _ in range(50):
            if socket.sent:
                break
            await asyncio.sleep(0.1)
    finally:
        listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listener_task
        await listener_client.aclose()

    assert socket.sent == [{"type": "notification", "hello": "world"}]

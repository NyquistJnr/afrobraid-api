"""Real-time push to connected clients, fanned out through Redis pub/sub so
it works regardless of which process holds the socket - the API can run
multiple uvicorn workers, and events are also published from the arq worker
process (see e.g. app.modules.chat.tasks), which never holds a socket at all.

Each API process keeps a `ConnectionManager` of the WebSocket connections it
personally holds, plus one background task (started in app.main's lifespan)
that psubscribes to `ws:user:*` and forwards anything published there to any
locally-held connection for that user. Publishing is fire-and-forget: the
underlying data (a chat message, a notification, ...) is already durably
committed to Postgres before anything is published here, so a client that
was offline just fetches current state over REST on reconnect instead of
replaying missed events.
"""

import json
import logging
import uuid
from collections import defaultdict

from fastapi import WebSocket
from redis.asyncio import Redis

from app.core.redis import get_redis_client

logger = logging.getLogger("app.ws")

_CHANNEL_PREFIX = "ws:user:"


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)

    def connect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        self._connections[user_id].add(websocket)

    def disconnect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        connections = self._connections.get(user_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: uuid.UUID, payload: dict) -> None:
        for connection in list(self._connections.get(user_id, ())):
            try:
                await connection.send_json(payload)
            except Exception:
                logger.exception("Failed sending ws payload to user %s", user_id)


manager = ConnectionManager()


def _channel_for(user_id: uuid.UUID) -> str:
    return f"{_CHANNEL_PREFIX}{user_id}"


async def publish_event(user_id: uuid.UUID, event: dict) -> None:
    """Fire-and-forget publish - safe to call from a request handler or an
    arq task, each of which gets its own short-lived Redis connection backed
    by the shared process-wide connection pool."""
    redis_client = get_redis_client()
    try:
        await redis_client.publish(_channel_for(user_id), json.dumps(event))
    finally:
        await redis_client.aclose()


async def redis_listener(redis_client: Redis) -> None:
    """Long-running task (one per API process, started in app.main's
    lifespan) that bridges Redis pub/sub events to this process's locally
    connected WebSockets."""
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe(f"{_CHANNEL_PREFIX}*")
    try:
        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue
            channel = message["channel"]
            try:
                user_id = uuid.UUID(channel[len(_CHANNEL_PREFIX) :])
                payload = json.loads(message["data"])
            except (ValueError, json.JSONDecodeError):
                logger.warning("Dropping malformed ws pub/sub message on %r", channel)
                continue
            await manager.send_to_user(user_id, payload)
    finally:
        await pubsub.punsubscribe(f"{_CHANNEL_PREFIX}*")
        await pubsub.aclose()

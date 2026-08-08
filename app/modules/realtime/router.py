import uuid

import jwt
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ws
from app.core.database import get_db
from app.core.security import decode_access_token
from app.modules.users.repository import get_user_by_id

router = APIRouter(tags=["Realtime"])

# WebSocket handshakes can't carry an Authorization header from a browser
# client, so the access token travels as a query param instead - same JWT
# used everywhere else, just a different transport. 4401 mirrors the
# app's usual 401 (custom codes must be >= 4000 per the WS spec).
_UNAUTHORIZED_CLOSE_CODE = 4401


@router.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket, db: AsyncSession = Depends(get_db)) -> None:
    """One persistent connection per client, pushing chat messages and
    notifications as they happen (app.core.ws). This is a live nudge only -
    the underlying data is already durable in Postgres before anything is
    published here, so a client fetches current state over REST on
    (re)connect rather than relying on this for delivery guarantees."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=_UNAUTHORIZED_CLOSE_CODE)
        return

    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        await websocket.close(code=_UNAUTHORIZED_CLOSE_CODE)
        return

    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        await websocket.close(code=_UNAUTHORIZED_CLOSE_CODE)
        return

    await websocket.accept()
    ws.manager.connect(user_id, websocket)
    try:
        while True:
            # Clients don't need to send anything - this just parks the
            # coroutine until the socket closes so `finally` can clean up.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws.manager.disconnect(user_id, websocket)

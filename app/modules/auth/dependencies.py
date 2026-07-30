import uuid

import jwt
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenRoleError, InvalidAccessTokenError, UserNotActiveError
from app.core.security import decode_access_token
from app.modules.users.models import User, UserType
from app.modules.users.repository import get_user_by_id


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise InvalidAccessTokenError()

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise InvalidAccessTokenError() from exc

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidAccessTokenError() from exc

    user = await get_user_by_id(db, user_id)
    if not user:
        raise InvalidAccessTokenError()
    if not user.is_active:
        raise UserNotActiveError()

    return user


def require_roles(*roles: UserType):
    """Dependency factory for role-gated endpoints (e.g. BRAIDER-only or ADMIN-only routes)."""

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.user_type not in roles:
            raise ForbiddenRoleError()
        return user

    return dependency

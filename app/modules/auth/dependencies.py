import uuid

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenRoleError, InvalidAccessTokenError, UserNotActiveError
from app.core.security import decode_access_token
from app.modules.users.models import User, UserType
from app.modules.users.repository import get_user_by_id

# auto_error=False so a missing/malformed header falls through to our own
# InvalidAccessTokenError (localized, consistent error shape) instead of
# FastAPI's default 403. Using this as a dependency (rather than a plain
# Header) is also what makes FastAPI register the "Authorize" bearer-token
# button in the Swagger UI.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise InvalidAccessTokenError()

    token = credentials.credentials
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

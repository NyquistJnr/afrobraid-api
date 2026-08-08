import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import AuthIdentity, AuthProvider, User, UserType


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def list_full_names(db: AsyncSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Batched display-name lookup - avoids one query per row when rendering
    a list (e.g. a braider's bookings, each naming its customer)."""
    if not user_ids:
        return {}
    result = await db.execute(
        select(User.id, User.first_name, User.last_name).where(User.id.in_(user_ids))
    )
    return {row.id: f"{row.first_name} {row.last_name or ''}".strip() for row in result.all()}


async def get_user_by_phone(db: AsyncSession, phone_number: str) -> User | None:
    result = await db.execute(select(User).where(User.phone_number == phone_number))
    return result.scalar_one_or_none()


async def get_identity(
    db: AsyncSession, provider: AuthProvider, provider_user_id: str
) -> AuthIdentity | None:
    result = await db.execute(
        select(AuthIdentity).where(
            AuthIdentity.provider == provider,
            AuthIdentity.provider_user_id == provider_user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    *,
    first_name: str,
    last_name: str | None,
    email: str,
    phone_number: str | None,
    password_hash: str | None,
    user_type: UserType,
    is_email_verified: bool,
) -> User:
    user = User(
        first_name=first_name,
        last_name=last_name,
        email=email.lower(),
        phone_number=phone_number,
        password_hash=password_hash,
        user_type=user_type,
        is_email_verified=is_email_verified,
    )
    db.add(user)
    await db.flush()
    return user


async def create_auth_identity(
    db: AsyncSession, *, user_id: uuid.UUID, provider: AuthProvider, provider_user_id: str
) -> AuthIdentity:
    identity = AuthIdentity(user_id=user_id, provider=provider, provider_user_id=provider_user_id)
    db.add(identity)
    await db.flush()
    return identity

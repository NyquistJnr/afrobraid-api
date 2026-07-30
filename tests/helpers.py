import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.modules.users import repository as users_repo
from app.modules.users.models import User, UserType


async def create_user_with_token(
    db_session: AsyncSession, *, user_type: UserType, email: str | None = None
) -> tuple[User, str]:
    """Creates a user directly (bypassing signup, which blocks ADMIN creation
    and requires OTP email verification) and mints a matching access token,
    for tests that need a BRAIDER or ADMIN identity without exercising auth."""
    user = await users_repo.create_user(
        db_session,
        first_name="Test",
        last_name="User",
        email=email or f"{uuid.uuid4()}@example.com",
        phone_number=None,
        password_hash=None,
        user_type=user_type,
        is_email_verified=True,
    )
    await db_session.commit()
    token, _ = create_access_token(user_id=user.id, user_type=user.user_type.value)
    return user, token

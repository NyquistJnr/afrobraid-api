import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PhoneAlreadyExistsError
from app.modules.users import repository as users_repo
from app.modules.users.schemas import UserProfileUpdateRequest, UserPublic


async def get_profile(db: AsyncSession, user_id: uuid.UUID) -> UserPublic:
    user = await users_repo.get_user_by_id(db, user_id)
    return UserPublic.model_validate(user)


async def update_profile(
    db: AsyncSession, user_id: uuid.UUID, *, data: UserProfileUpdateRequest
) -> UserPublic:
    user = await users_repo.get_user_by_id(db, user_id)
    assert user is not None

    updates = data.model_dump(exclude_unset=True)

    if "phone_number" in updates:
        phone_number = updates["phone_number"]
        if phone_number and phone_number != user.phone_number:
            existing = await users_repo.get_user_by_phone(db, phone_number)
            if existing and existing.id != user.id:
                raise PhoneAlreadyExistsError()
        user.phone_number = phone_number

    if "first_name" in updates:
        user.first_name = updates["first_name"]
    if "last_name" in updates:
        user.last_name = updates["last_name"]

    await db.commit()
    await db.refresh(user)
    return UserPublic.model_validate(user)

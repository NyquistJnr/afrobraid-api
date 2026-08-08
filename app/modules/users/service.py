import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import InvalidChatLocaleError, PhoneAlreadyExistsError
from app.modules.users import repository as users_repo
from app.modules.users.schemas import UserProfileUpdateRequest, UserPublic

settings = get_settings()


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

    if "chat_locale" in updates:
        chat_locale = updates["chat_locale"]
        if chat_locale is not None and chat_locale not in settings.supported_locales_list:
            raise InvalidChatLocaleError()
        user.chat_locale = chat_locale

    await db.commit()
    await db.refresh(user)
    return UserPublic.model_validate(user)

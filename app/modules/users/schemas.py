import uuid

from pydantic import BaseModel, ConfigDict

from app.modules.users.models import UserType


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str | None
    email: str
    phone_number: str | None
    user_type: UserType

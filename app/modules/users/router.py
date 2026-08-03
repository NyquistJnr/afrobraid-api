from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import APIResponse
from app.modules.auth.dependencies import get_current_user
from app.modules.users import service
from app.modules.users.models import User
from app.modules.users.schemas import UserProfileUpdateRequest, UserPublic

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("/me", response_model=APIResponse[UserPublic])
async def get_my_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[UserPublic]:
    result = await service.get_profile(db, user.id)
    return APIResponse(data=result)


@router.patch("/me", response_model=APIResponse[UserPublic])
async def update_my_profile(
    payload: UserProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[UserPublic]:
    result = await service.update_profile(db, user.id, data=payload)
    return APIResponse(data=result)

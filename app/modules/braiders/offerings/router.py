import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.braiders.offerings import service
from app.modules.braiders.offerings.schemas import (
    BraiderStyleCreateRequest,
    BraiderStyleResponse,
    BraiderStyleUpdateRequest,
)
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/braiders/onboarding/services", tags=["Braider Onboarding - Services"])

_require_braider = require_roles(UserType.BRAIDER)


@router.get("", response_model=APIResponse[list[BraiderStyleResponse]])
async def list_braider_styles(
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[BraiderStyleResponse]]:
    result = await service.list_braider_styles(db, user.id)
    return APIResponse(data=result)


@router.post("", response_model=APIResponse[BraiderStyleResponse], status_code=status.HTTP_201_CREATED)
async def create_braider_style(
    payload: BraiderStyleCreateRequest,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BraiderStyleResponse]:
    result = await service.create_braider_style(db, user.id, data=payload)
    return APIResponse(data=result)


@router.put("/{braider_style_id}", response_model=APIResponse[BraiderStyleResponse])
async def update_braider_style(
    braider_style_id: uuid.UUID,
    payload: BraiderStyleUpdateRequest,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BraiderStyleResponse]:
    result = await service.update_braider_style(db, user.id, braider_style_id, data=payload)
    return APIResponse(data=result)


@router.delete("/{braider_style_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_braider_style(
    braider_style_id: uuid.UUID,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_braider_style(db, user.id, braider_style_id)

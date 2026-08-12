import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.braiders import admin_service as service
from app.modules.braiders.schemas import AdminBraiderOnboardingResponse
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/admin/braiders", tags=["Admin - Braiders"])

_require_admin = require_roles(UserType.ADMIN)


@router.get(
    "/{braider_id}/onboarding",
    response_model=APIResponse[AdminBraiderOnboardingResponse],
    summary="Get a braider's onboarding progress",
    description="Returns all 8 onboarding steps with completion flags and timestamps.",
)
async def get_braider_onboarding(
    braider_id: uuid.UUID,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminBraiderOnboardingResponse]:
    result = await service.get_braider_onboarding(db, braider_id)
    return APIResponse(data=result)

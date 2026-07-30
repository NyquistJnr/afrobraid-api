from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.braiders.service_location import service
from app.modules.braiders.service_location.schemas import (
    ServiceLocationResponse,
    ServiceLocationUpdateRequest,
)
from app.modules.users.models import User, UserType

router = APIRouter(
    prefix="/api/v1/braiders/onboarding/service-location",
    tags=["Braider Onboarding - Service Location"],
)

_require_braider = require_roles(UserType.BRAIDER)


@router.get(
    "",
    response_model=APIResponse[ServiceLocationResponse],
    summary="Get your service location",
)
async def get_service_location(
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ServiceLocationResponse]:
    result = await service.get_service_location(db, user.id)
    return APIResponse(data=result)


@router.put(
    "",
    response_model=APIResponse[ServiceLocationResponse],
    summary="Update your service location",
    description=(
        "Partial update, like business-info - only send what you're changing. "
        "`location_type` (null / HOME_STUDIO / SALON) and `offers_mobile` are "
        "independent, so you can have a salon chair and travel too. "
        "`is_complete` in the response reflects current data; the "
        "SERVICE_LOCATION onboarding step completes automatically the moment "
        "it becomes true, and un-completes if you later clear something it needs."
    ),
)
async def update_service_location(
    payload: ServiceLocationUpdateRequest,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ServiceLocationResponse]:
    result = await service.update_service_location(db, user.id, data=payload)
    return APIResponse(data=result)

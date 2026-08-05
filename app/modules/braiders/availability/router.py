import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.braiders.availability import service
from app.modules.braiders.availability.schemas import (
    AvailabilityExceptionCreateRequest,
    AvailabilityExceptionResponse,
    AvailabilitySettingsResponse,
    AvailabilitySettingsUpdateRequest,
    AvailableSlotResponse,
    WeeklyWindowCreateRequest,
    WeeklyWindowResponse,
    WeeklyWindowUpdateRequest,
)
from app.modules.users.models import User, UserType

router = APIRouter(
    prefix="/api/v1/braiders/onboarding/availability",
    tags=["Braider Onboarding - Availability"],
)
public_router = APIRouter(prefix="/api/v1/braiders", tags=["Braider Availability"])

_require_braider = require_roles(UserType.BRAIDER)


@router.get(
    "/settings",
    response_model=APIResponse[AvailabilitySettingsResponse],
    summary="Get your availability settings",
)
async def get_settings(
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AvailabilitySettingsResponse]:
    result = await service.get_settings(db, user.id)
    return APIResponse(data=result)


@router.put(
    "/settings",
    response_model=APIResponse[AvailabilitySettingsResponse],
    summary="Update your availability settings",
    description="Partial update - only send what you're changing.",
)
async def update_settings(
    payload: AvailabilitySettingsUpdateRequest,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AvailabilitySettingsResponse]:
    result = await service.update_settings(db, user.id, data=payload)
    return APIResponse(data=result)


@router.get(
    "/weekly-windows",
    response_model=APIResponse[list[WeeklyWindowResponse]],
    summary="List your recurring weekly hours",
)
async def list_weekly_windows(
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[WeeklyWindowResponse]]:
    result = await service.list_weekly_windows(db, user.id)
    return APIResponse(data=result)


@router.post(
    "/weekly-windows",
    response_model=APIResponse[WeeklyWindowResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add a recurring weekly window",
    description=(
        "Add multiple windows for the same day for a split shift, e.g. "
        "09:00-12:00 and 13:00-17:00. Completes the AVAILABILITY onboarding "
        "step the first time you add one."
    ),
)
async def create_weekly_window(
    payload: WeeklyWindowCreateRequest,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[WeeklyWindowResponse]:
    result = await service.create_weekly_window(db, user.id, data=payload)
    return APIResponse(data=result)


@router.patch(
    "/weekly-windows/{window_id}",
    response_model=APIResponse[WeeklyWindowResponse],
    summary="Edit a recurring weekly window",
)
async def update_weekly_window(
    window_id: uuid.UUID,
    payload: WeeklyWindowUpdateRequest,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[WeeklyWindowResponse]:
    result = await service.update_weekly_window(db, user.id, window_id, data=payload)
    return APIResponse(data=result)


@router.delete(
    "/weekly-windows/{window_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a recurring weekly window",
)
async def delete_weekly_window(
    window_id: uuid.UUID,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_weekly_window(db, user.id, window_id)


@router.get(
    "/exceptions",
    response_model=APIResponse[list[AvailabilityExceptionResponse]],
    summary="List your date-specific exceptions",
)
async def list_exceptions(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[AvailabilityExceptionResponse]]:
    result = await service.list_exceptions(db, user.id, date_from=date_from, date_to=date_to)
    return APIResponse(data=result)


@router.post(
    "/exceptions",
    response_model=APIResponse[AvailabilityExceptionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add a date-specific exception",
    description=(
        "Use `CLOSED` to block a whole date (e.g. a holiday), or `CUSTOM_HOURS` "
        "with `start_time`/`end_time` to override your usual hours for one date "
        "instead of your recurring weekly pattern."
    ),
)
async def create_exception(
    payload: AvailabilityExceptionCreateRequest,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AvailabilityExceptionResponse]:
    result = await service.create_exception(db, user.id, data=payload)
    return APIResponse(data=result)


@router.delete(
    "/exceptions/{exception_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a date-specific exception",
)
async def delete_exception(
    exception_id: uuid.UUID,
    user: User = Depends(_require_braider),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_exception(db, user.id, exception_id)


@public_router.get(
    "/{braider_id}/availability/slots",
    response_model=APIResponse[list[AvailableSlotResponse]],
    summary="Get bookable slots for a braider's style",
    description=(
        "Computed from the braider's weekly hours, date exceptions, the "
        "style's duration, and already-booked times - returned as UTC "
        "start/end datetimes."
    ),
)
async def get_available_slots(
    braider_id: uuid.UUID,
    style_id: uuid.UUID = Query(...),
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[AvailableSlotResponse]]:
    result = await service.compute_available_slots(
        db, braider_id, style_id, date_from=date_from, date_to=date_to
    )
    return APIResponse(data=result)

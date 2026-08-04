import uuid

from fastapi import APIRouter, Depends, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import ip_rate_limiter
from app.core.redis import get_redis
from app.core.response import APIResponse
from app.modules.bookings.calculations import service
from app.modules.bookings.calculations.schemas import (
    BookingCalculationInput,
    BookingCalculationPreviewResponse,
    BookingCalculationResponse,
    BookingCalculationUpdateRequest,
)

router = APIRouter(
    prefix="/api/v1/booking-calculations",
    tags=["Booking Calculator"],
    dependencies=[
        Depends(ip_rate_limiter(key_prefix="booking_calc", limit=30, window_seconds=3600))
    ],
)


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/preview", response_model=APIResponse[BookingCalculationPreviewResponse])
async def preview_booking_calculation(
    payload: BookingCalculationInput,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> APIResponse[BookingCalculationPreviewResponse]:
    """Stateless price preview - writes nothing to the database. Most
    clients building a live quote UI will want this over the persisted
    CRUD below."""
    result = await service.preview(db, redis, data=payload, locale=_locale(request))
    return APIResponse(data=result)


@router.post(
    "", response_model=APIResponse[BookingCalculationResponse], status_code=status.HTTP_201_CREATED
)
async def create_booking_calculation(
    payload: BookingCalculationInput,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> APIResponse[BookingCalculationResponse]:
    result = await service.create_calculation(
        db,
        redis,
        data=payload,
        locale=_locale(request),
        user_id=None,
        client_ip=_client_ip(request),
    )
    return APIResponse(data=result)


@router.get("/{calculation_id}", response_model=APIResponse[BookingCalculationResponse])
async def get_booking_calculation(
    calculation_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BookingCalculationResponse]:
    result = await service.get_calculation(db, calculation_id, locale=_locale(request))
    return APIResponse(data=result)


@router.patch("/{calculation_id}", response_model=APIResponse[BookingCalculationResponse])
async def update_booking_calculation(
    calculation_id: uuid.UUID,
    payload: BookingCalculationUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> APIResponse[BookingCalculationResponse]:
    result = await service.update_calculation(
        db, redis, calculation_id, data=payload, locale=_locale(request)
    )
    return APIResponse(data=result)


@router.delete("/{calculation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_booking_calculation(
    calculation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_calculation(db, calculation_id)

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import Currency
from app.modules.bookings.calculations.models import (
    BookingCalculation,
    BookingCalculationAddon,
    BookingCalculationStatus,
)
from app.modules.platform_settings.models import SettingValueType


async def get_calculation_by_id(
    db: AsyncSession, calculation_id: uuid.UUID
) -> BookingCalculation | None:
    return await db.get(BookingCalculation, calculation_id)


async def list_addons(
    db: AsyncSession, booking_calculation_id: uuid.UUID
) -> list[BookingCalculationAddon]:
    result = await db.execute(
        select(BookingCalculationAddon).where(
            BookingCalculationAddon.booking_calculation_id == booking_calculation_id
        )
    )
    return list(result.scalars().all())


async def create_calculation(
    db: AsyncSession,
    *,
    braider_id: uuid.UUID,
    braider_style_id: uuid.UUID,
    style_id: uuid.UUID,
    style_variation_id: uuid.UUID | None,
    braider_style_variation_id: uuid.UUID | None,
    is_mobile: bool,
    currency: Currency,
    duration_minutes: int,
    service_subtotal: Decimal,
    travel_fee: Decimal,
    subtotal: Decimal,
    platform_fee_type: SettingValueType,
    platform_fee_value: Decimal,
    platform_fee: Decimal,
    vat_service_type: SettingValueType,
    vat_service_value: Decimal,
    vat_on_service: Decimal,
    vat_platform_fee_type: SettingValueType,
    vat_platform_fee_value: Decimal,
    vat_on_platform_fee: Decimal,
    vat_total: Decimal,
    total: Decimal,
    deposit_type: SettingValueType,
    deposit_value: Decimal,
    deposit_amount: Decimal,
    balance_amount: Decimal,
    expires_at: datetime,
    created_by_user_id: uuid.UUID | None,
    client_ip_hash: str | None,
) -> BookingCalculation:
    calculation = BookingCalculation(
        braider_id=braider_id,
        braider_style_id=braider_style_id,
        style_id=style_id,
        style_variation_id=style_variation_id,
        braider_style_variation_id=braider_style_variation_id,
        is_mobile=is_mobile,
        currency=currency,
        duration_minutes=duration_minutes,
        service_subtotal=service_subtotal,
        travel_fee=travel_fee,
        subtotal=subtotal,
        platform_fee_type=platform_fee_type,
        platform_fee_value=platform_fee_value,
        platform_fee=platform_fee,
        vat_service_type=vat_service_type,
        vat_service_value=vat_service_value,
        vat_on_service=vat_on_service,
        vat_platform_fee_type=vat_platform_fee_type,
        vat_platform_fee_value=vat_platform_fee_value,
        vat_on_platform_fee=vat_on_platform_fee,
        vat_total=vat_total,
        total=total,
        deposit_type=deposit_type,
        deposit_value=deposit_value,
        deposit_amount=deposit_amount,
        balance_amount=balance_amount,
        status=BookingCalculationStatus.DRAFT,
        expires_at=expires_at,
        created_by_user_id=created_by_user_id,
        client_ip_hash=client_ip_hash,
    )
    db.add(calculation)
    await db.flush()
    return calculation


async def add_addon(
    db: AsyncSession,
    *,
    booking_calculation_id: uuid.UUID,
    braider_style_addon_id: uuid.UUID,
    addon_id: uuid.UUID,
    price: Decimal,
    is_required: bool,
) -> BookingCalculationAddon:
    row = BookingCalculationAddon(
        booking_calculation_id=booking_calculation_id,
        braider_style_addon_id=braider_style_addon_id,
        addon_id=addon_id,
        price=price,
        is_required=is_required,
    )
    db.add(row)
    await db.flush()
    return row


async def delete_addons(db: AsyncSession, booking_calculation_id: uuid.UUID) -> None:
    await db.execute(
        delete(BookingCalculationAddon).where(
            BookingCalculationAddon.booking_calculation_id == booking_calculation_id
        )
    )
    await db.flush()


async def delete_calculation(db: AsyncSession, calculation: BookingCalculation) -> None:
    await db.delete(calculation)
    await db.flush()


async def delete_expired_draft_calculations(db: AsyncSession, *, limit: int) -> int:
    """Batched cleanup for the `expire_booking_calculations` cron - deletes
    at most `limit` expired DRAFT rows per call so a large backlog doesn't
    hold a long-running DELETE against the table."""
    result = await db.execute(
        delete(BookingCalculation).where(
            BookingCalculation.id.in_(
                select(BookingCalculation.id)
                .where(
                    BookingCalculation.status == BookingCalculationStatus.DRAFT,
                    BookingCalculation.expires_at < datetime.now(UTC),
                )
                .limit(limit)
            )
        )
    )
    return result.rowcount or 0

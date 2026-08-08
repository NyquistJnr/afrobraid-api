import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.currency import Currency
from app.core.pagination import PaginationParams, paginate
from app.modules.bookings.enums import (
    CALENDAR_BLOCKING_STATUSES,
    BalanceChargeState,
    BookingItemType,
    BookingStatus,
    PaymentPurpose,
    PaymentSchedule,
    PaymentStatus,
)
from app.modules.bookings.models import Booking, BookingItem, BookingPayment
from app.modules.braiders.models import BraiderProfile
from app.modules.platform_settings.models import SettingValueType
from app.modules.styles.models import Style
from app.modules.users.models import User


async def get_booking_by_id(db: AsyncSession, booking_id: uuid.UUID) -> Booking | None:
    return await db.get(Booking, booking_id)


async def get_booking_by_calculation_id(
    db: AsyncSession, booking_calculation_id: uuid.UUID
) -> Booking | None:
    result = await db.execute(
        select(Booking).where(Booking.booking_calculation_id == booking_calculation_id)
    )
    return result.scalar_one_or_none()


async def list_items(db: AsyncSession, booking_id: uuid.UUID) -> list[BookingItem]:
    result = await db.execute(select(BookingItem).where(BookingItem.booking_id == booking_id))
    return list(result.scalars().all())


async def list_payments(db: AsyncSession, booking_id: uuid.UUID) -> list[BookingPayment]:
    result = await db.execute(
        select(BookingPayment)
        .where(BookingPayment.booking_id == booking_id)
        .order_by(BookingPayment.created_at)
    )
    return list(result.scalars().all())


async def get_payment_by_stripe_intent_id(
    db: AsyncSession, stripe_payment_intent_id: str
) -> BookingPayment | None:
    result = await db.execute(
        select(BookingPayment).where(
            BookingPayment.stripe_payment_intent_id == stripe_payment_intent_id
        )
    )
    return result.scalar_one_or_none()


async def get_pending_payment(
    db: AsyncSession, booking_id: uuid.UUID, purpose: PaymentPurpose
) -> BookingPayment | None:
    result = await db.execute(
        select(BookingPayment).where(
            BookingPayment.booking_id == booking_id,
            BookingPayment.purpose == purpose,
            BookingPayment.status == PaymentStatus.PENDING,
        )
    )
    return result.scalars().first()


def _apply_common_filters(
    stmt,
    *,
    status: BookingStatus | None,
    date_from: date | None,
    date_to: date | None,
):
    """Shared status/appointment-date filters for both the customer's and
    the braider's booking lists. Dates bound `starts_at` (the appointment
    time), not `created_at` - what a user wants to browse by is when the
    appointment is, not when they booked it. Bounds are whole UTC calendar
    days, inclusive on both ends."""
    if status is not None:
        stmt = stmt.where(Booking.status == status)
    if date_from is not None:
        stmt = stmt.where(Booking.starts_at >= datetime.combine(date_from, time.min, tzinfo=UTC))
    if date_to is not None:
        stmt = stmt.where(
            Booking.starts_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC)
        )
    return stmt


async def list_bookings_for_customer(
    db: AsyncSession,
    customer_id: uuid.UUID,
    *,
    params: PaginationParams,
    status: BookingStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
) -> tuple[list[Booking], object]:
    stmt = select(Booking).where(Booking.customer_id == customer_id)
    stmt = _apply_common_filters(stmt, status=status, date_from=date_from, date_to=date_to)

    if search:
        pattern = f"%{search}%"
        braider_user = aliased(User)
        stmt = (
            stmt.join(Style, Style.id == Booking.style_id)
            .join(BraiderProfile, BraiderProfile.id == Booking.braider_id)
            .join(braider_user, braider_user.id == BraiderProfile.user_id)
            .where(
                or_(
                    Style.name_en.ilike(pattern),
                    Style.name_de.ilike(pattern),
                    Style.name_fr.ilike(pattern),
                    BraiderProfile.business_name.ilike(pattern),
                    braider_user.first_name.ilike(pattern),
                    braider_user.last_name.ilike(pattern),
                )
            )
        )

    stmt = stmt.order_by(Booking.starts_at.desc())
    return await paginate(db, stmt, params)


async def list_bookings_for_braider(
    db: AsyncSession,
    braider_id: uuid.UUID,
    *,
    params: PaginationParams,
    status: BookingStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
) -> tuple[list[Booking], object]:
    stmt = select(Booking).where(Booking.braider_id == braider_id)
    stmt = _apply_common_filters(stmt, status=status, date_from=date_from, date_to=date_to)

    if search:
        pattern = f"%{search}%"
        customer_user = aliased(User)
        stmt = (
            stmt.join(Style, Style.id == Booking.style_id)
            .join(customer_user, customer_user.id == Booking.customer_id)
            .where(
                or_(
                    Style.name_en.ilike(pattern),
                    Style.name_de.ilike(pattern),
                    Style.name_fr.ilike(pattern),
                    customer_user.first_name.ilike(pattern),
                    customer_user.last_name.ilike(pattern),
                )
            )
        )

    stmt = stmt.order_by(Booking.starts_at.desc())
    return await paginate(db, stmt, params)


async def list_blocked_ranges(
    db: AsyncSession, braider_id: uuid.UUID, *, range_start: datetime, range_end: datetime
) -> list[tuple[datetime, datetime]]:
    """Every (blocked_from, blocked_until) span that currently occupies this
    braider's calendar and overlaps [range_start, range_end) - used by
    `compute_available_slots` to subtract already-booked time. Mirrors the
    `ex_bookings_no_overlap` exclusion constraint's own status filter
    (CALENDAR_BLOCKING_STATUSES) so a slot this returns as "free" really is
    insertable."""
    result = await db.execute(
        select(Booking.blocked_from, Booking.blocked_until).where(
            Booking.braider_id == braider_id,
            Booking.status.in_(CALENDAR_BLOCKING_STATUSES),
            Booking.blocked_from < range_end,
            Booking.blocked_until > range_start,
        )
    )
    return [(row.blocked_from, row.blocked_until) for row in result.all()]


async def expire_stale_holds(db: AsyncSession, *, limit: int) -> int:
    """Flips PENDING_PAYMENT bookings past their hold_expires_at to EXPIRED,
    in batches - EXPIRED isn't in CALENDAR_BLOCKING_STATUSES, so this is what
    actually releases the exclusion-constraint hold on the slot for an
    abandoned checkout (payment never completed)."""
    result = await db.execute(
        update(Booking)
        .where(
            Booking.id.in_(
                select(Booking.id)
                .where(
                    Booking.status == BookingStatus.PENDING_PAYMENT,
                    Booking.hold_expires_at.is_not(None),
                    Booking.hold_expires_at < datetime.now(UTC),
                )
                .limit(limit)
            )
        )
        .values(status=BookingStatus.EXPIRED)
    )
    return result.rowcount or 0


async def create_booking(
    db: AsyncSession,
    *,
    reference: str,
    customer_id: uuid.UUID,
    braider_id: uuid.UUID,
    booking_calculation_id: uuid.UUID,
    braider_style_id: uuid.UUID,
    style_id: uuid.UUID,
    style_variation_id: uuid.UUID | None,
    braider_style_variation_id: uuid.UUID | None,
    is_mobile: bool,
    country: str,
    client_address: str | None,
    client_latitude: Decimal | None,
    client_longitude: Decimal | None,
    currency: Currency,
    duration_minutes: int,
    starts_at: datetime,
    ends_at: datetime,
    braider_timezone: str,
    blocked_from: datetime,
    blocked_until: datetime,
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
    payment_schedule: PaymentSchedule,
    braider_share_total: Decimal,
    braider_share_deposit: Decimal,
    braider_share_balance: Decimal,
    hold_expires_at: datetime | None,
    cancellation_cutoff_at: datetime,
    balance_charge_due_at: datetime | None,
    balance_charge_state: BalanceChargeState,
    stripe_customer_id: str | None,
    locale: str,
    terms_version: str,
    terms_accepted_at: datetime,
) -> Booking:
    booking = Booking(
        reference=reference,
        customer_id=customer_id,
        braider_id=braider_id,
        booking_calculation_id=booking_calculation_id,
        braider_style_id=braider_style_id,
        style_id=style_id,
        style_variation_id=style_variation_id,
        braider_style_variation_id=braider_style_variation_id,
        is_mobile=is_mobile,
        country=country,
        client_address=client_address,
        client_latitude=client_latitude,
        client_longitude=client_longitude,
        currency=currency,
        duration_minutes=duration_minutes,
        starts_at=starts_at,
        ends_at=ends_at,
        braider_timezone=braider_timezone,
        blocked_from=blocked_from,
        blocked_until=blocked_until,
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
        payment_schedule=payment_schedule,
        braider_share_total=braider_share_total,
        braider_share_deposit=braider_share_deposit,
        braider_share_balance=braider_share_balance,
        status=BookingStatus.PENDING_PAYMENT,
        hold_expires_at=hold_expires_at,
        cancellation_cutoff_at=cancellation_cutoff_at,
        balance_charge_due_at=balance_charge_due_at,
        balance_charge_state=balance_charge_state,
        stripe_customer_id=stripe_customer_id,
        locale=locale,
        terms_version=terms_version,
        terms_accepted_at=terms_accepted_at,
    )
    db.add(booking)
    await db.flush()
    return booking


async def add_item(
    db: AsyncSession,
    *,
    booking_id: uuid.UUID,
    item_type: BookingItemType,
    name_en: str | None,
    name_de: str | None,
    name_fr: str | None,
    quantity: int = 1,
    unit_amount: Decimal,
    line_amount: Decimal,
    is_required: bool = False,
    vat_rate: Decimal | None = None,
    source_style_id: uuid.UUID | None = None,
    source_style_variation_id: uuid.UUID | None = None,
    source_addon_id: uuid.UUID | None = None,
    source_braider_style_addon_id: uuid.UUID | None = None,
) -> BookingItem:
    item = BookingItem(
        booking_id=booking_id,
        item_type=item_type,
        name_en=name_en,
        name_de=name_de,
        name_fr=name_fr,
        quantity=quantity,
        unit_amount=unit_amount,
        line_amount=line_amount,
        is_required=is_required,
        vat_rate=vat_rate,
        source_style_id=source_style_id,
        source_style_variation_id=source_style_variation_id,
        source_addon_id=source_addon_id,
        source_braider_style_addon_id=source_braider_style_addon_id,
    )
    db.add(item)
    await db.flush()
    return item


async def create_payment(
    db: AsyncSession,
    *,
    booking_id: uuid.UUID,
    purpose: PaymentPurpose,
    amount_minor: int,
    currency: Currency,
    braider_share_minor: int,
    stripe_payment_intent_id: str | None,
    idempotency_key: str,
    is_off_session: bool,
    transfer_group: str,
    attempt_number: int = 1,
) -> BookingPayment:
    payment = BookingPayment(
        booking_id=booking_id,
        purpose=purpose,
        status=PaymentStatus.PENDING,
        amount_minor=amount_minor,
        currency=currency,
        braider_share_minor=braider_share_minor,
        stripe_payment_intent_id=stripe_payment_intent_id,
        idempotency_key=idempotency_key,
        is_off_session=is_off_session,
        transfer_group=transfer_group,
        attempt_number=attempt_number,
    )
    db.add(payment)
    await db.flush()
    return payment

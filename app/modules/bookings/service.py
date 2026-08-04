import uuid
import secrets
from datetime import datetime, timedelta, UTC
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.exceptions import (
    DoubleBookingError,
    BookingNotFoundError,
    BraiderNotPayableError,
    InvalidBookingTransitionError,
)
from app.core.money import to_minor_units
from app.core.currency import MINIMUM_CHARGE_MINOR_UNITS
from app.modules.bookings.calculations.models import BookingCalculation, BookingCalculationStatus
from app.modules.bookings.enums import (
    BookingStatus,
    PaymentPurpose,
    PaymentSchedule,
    PaymentStatus,
    BookingItemType,
    BalanceChargeState,
)
from app.modules.bookings.models import Booking, BookingItem, BookingPayment
from app.modules.bookings.payments import client as stripe_client
from app.modules.users.models import User


def _generate_booking_reference() -> str:
    # E.g. AB-7QK3M2
    chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ" # avoid 1,I,0,O
    suffix = "".join(secrets.choice(chars) for _ in range(6))
    return f"AB-{suffix}"


async def create_booking(
    db: AsyncSession,
    customer: User,
    calculation_id: uuid.UUID,
    starts_at: datetime,
) -> tuple[Booking, str | None]:
    now = datetime.now(UTC)
    
    # 1. Fetch calculation
    stmt = select(BookingCalculation).where(BookingCalculation.id == calculation_id)
    calc = (await db.execute(stmt)).scalar_one_or_none()
    if not calc:
        raise BookingNotFoundError()
        
    if calc.status != BookingCalculationStatus.DRAFT:
        raise InvalidBookingTransitionError(f"Calculation is already {calc.status.value}")
        
    if calc.expires_at < now:
        raise InvalidBookingTransitionError("Calculation has expired")

    # 2. Check Braider Payability (Stripe Connect)
    # The design says: must 409 unless charges_enabled AND payouts_enabled
    # We can fetch the braider's connect account.
    # Note: To avoid cyclical dependencies, we'll import repository here or just query it.
    from app.modules.braiders.payment_setup.models import StripeConnectAccount
    
    connect_stmt = select(StripeConnectAccount).where(StripeConnectAccount.user_id == calc.braider_id)
    connect_account = (await db.execute(connect_stmt)).scalar_one_or_none()
    
    if not connect_account or not connect_account.charges_enabled or not connect_account.payouts_enabled:
        raise BraiderNotPayableError()

    # 3. Determine schedule based on starts_at vs FULL_PAYMENT_THRESHOLD_HOURS
    ends_at = starts_at + timedelta(minutes=calc.duration_minutes)
    
    # Overlap buffer - assuming no buffer for now or we should read it from braider? 
    # The calculation doesn't store buffer, let's just use starts_at and ends_at as blocked range for now.
    blocked_from = starts_at
    blocked_until = ends_at
    
    hours_until = (starts_at - now).total_seconds() / 3600
    threshold = get_settings().booking_full_payment_threshold_hours
    margin = get_settings().booking_full_payment_margin_hours
    
    total_minor = to_minor_units(calc.total)
    
    if hours_until <= threshold:
        payment_schedule = PaymentSchedule.FULL_UPFRONT
        deposit_amount = calc.total
        balance_amount = Decimal("0.00")
        braider_share_deposit = calc.subtotal # Simplified logic, wait, need proper braider share calc
    else:
        payment_schedule = PaymentSchedule.DEPOSIT_THEN_BALANCE
        deposit_amount = calc.deposit_amount
        balance_amount = calc.balance_amount
        # Re-verify minimum charge logic? Pricing already did this in quote.
        
    # We must calculate braider share exactly.
    # Total braider share = total - platform_fee - vat_on_platform_fee
    braider_share_total = calc.total - calc.platform_fee - calc.vat_on_platform_fee
    
    if payment_schedule == PaymentSchedule.FULL_UPFRONT:
        braider_share_deposit = braider_share_total
        braider_share_balance = Decimal("0.00")
    else:
        # Deposit braider share = deposit_amount - platform_fee - vat_on_platform_fee (platform takes its cut upfront)
        braider_share_deposit = deposit_amount - calc.platform_fee - calc.vat_on_platform_fee
        if braider_share_deposit < 0:
            # If deposit is less than platform fee, platform takes all deposit, and rest from balance
            braider_share_deposit = Decimal("0.00")
        braider_share_balance = braider_share_total - braider_share_deposit

    deposit_minor = to_minor_units(deposit_amount)
    braider_share_deposit_minor = to_minor_units(braider_share_deposit)

    # 4. Create Booking
    cancellation_cutoff = starts_at - timedelta(hours=threshold)
    
    booking = Booking(
        reference=_generate_booking_reference(),
        customer_id=customer.id,
        braider_id=calc.braider_id,
        status=BookingStatus.PENDING_PAYMENT,
        
        starts_at=starts_at,
        ends_at=ends_at,
        blocked_from=blocked_from,
        blocked_until=blocked_until,
        braider_timezone="UTC", # TODO: Get from braider profile
        
        client_address=calc.client_address,
        client_latitude=calc.client_latitude,
        client_longitude=calc.client_longitude,
        
        subtotal=calc.subtotal,
        platform_fee=calc.platform_fee,
        vat_on_service=calc.vat_on_service,
        vat_on_platform_fee=calc.vat_on_platform_fee,
        vat_total=calc.vat_total,
        total=calc.total,
        deposit_amount=deposit_amount,
        
        braider_share_total=braider_share_total,
        braider_share_deposit=braider_share_deposit,
        braider_share_balance=braider_share_balance,
        
        platform_fee_type=calc.platform_fee_type,
        platform_fee_value=calc.platform_fee_value,
        vat_service_type=calc.vat_service_type,
        vat_service_value=calc.vat_service_value,
        vat_platform_fee_type=calc.vat_platform_fee_type,
        vat_platform_fee_value=calc.vat_platform_fee_value,
        deposit_type=calc.deposit_type,
        deposit_value=calc.deposit_value,
        
        braider_vat_status=None, # TODO
        braider_vat_number=None, # TODO
        
        payment_schedule=payment_schedule,
        cancellation_cutoff_at=cancellation_cutoff,
        balance_charge_due_at=starts_at - timedelta(hours=threshold + margin) if payment_schedule == PaymentSchedule.DEPOSIT_THEN_BALANCE else None,
        balance_charge_state=BalanceChargeState.SCHEDULED if payment_schedule == PaymentSchedule.DEPOSIT_THEN_BALANCE else None,
        
        stripe_customer_id=customer.stripe_customer_id,
        terms_version=get_settings().terms_version,
        terms_accepted_at=now,
        locale=get_settings().default_locale,
    )
    
    db.add(booking)
    
    # Line items
    # 1x Service
    db.add(BookingItem(
        booking=booking,
        item_type=BookingItemType.SERVICE,
        source_style_id=calc.style_id,
        line_amount=calc.service_subtotal,
        vat_rate=calc.vat_service_value,
    ))
    # Addons from DB
    from app.modules.bookings.calculations.models import BookingCalculationAddon
    addon_stmt = select(BookingCalculationAddon).where(BookingCalculationAddon.booking_calculation_id == calculation_id)
    addons = (await db.execute(addon_stmt)).scalars().all()
    for addon in addons:
        db.add(BookingItem(
            booking=booking,
            item_type=BookingItemType.ADDON,
            source_addon_id=addon.addon_id,
            source_braider_style_addon_id=addon.braider_style_addon_id,
            line_amount=addon.price,
            vat_rate=calc.vat_service_value,
        ))
        
    if calc.travel_fee > 0:
        db.add(BookingItem(
            booking=booking,
            item_type=BookingItemType.TRAVEL,
            line_amount=calc.travel_fee,
            vat_rate=calc.vat_service_value,
        ))

    # 5. Flush to catch Double Booking (23P01)
    try:
        await db.flush()
    except IntegrityError as e:
        if "ex_bookings_no_overlap" in str(e):
            raise DoubleBookingError()
        raise

    # 6. Consume calculation
    calc.status = BookingCalculationStatus.CONSUMED
    calc.consumed_by_booking_id = booking.id

    # 7. Stripe Customer / PaymentIntent
    if not customer.stripe_customer_id:
        customer.stripe_customer_id = stripe_client.create_customer(email=customer.email, name=customer.full_name)
    
    if deposit_minor > 0:
        pi_id, client_secret = stripe_client.create_payment_intent(
            customer_id=customer.stripe_customer_id,
            amount_minor=deposit_minor,
            currency=calc.currency.value,
            metadata={"booking_id": str(booking.id), "purpose": PaymentPurpose.DEPOSIT.value if payment_schedule == PaymentSchedule.DEPOSIT_THEN_BALANCE else PaymentPurpose.FULL.value},
            transfer_group=str(booking.id),
            setup_future_usage="off_session" if payment_schedule == PaymentSchedule.DEPOSIT_THEN_BALANCE else None,
        )
        
        payment = BookingPayment(
            booking=booking,
            purpose=PaymentPurpose.DEPOSIT if payment_schedule == PaymentSchedule.DEPOSIT_THEN_BALANCE else PaymentPurpose.FULL,
            status=PaymentStatus.PENDING,
            amount_minor=deposit_minor,
            braider_share_minor=braider_share_deposit_minor,
            stripe_payment_intent_id=pi_id,
            transfer_group=str(booking.id),
        )
        db.add(payment)
        await db.flush()
    else:
        # Zero-amount booking? Unlikely with minimum charges, but possible if full coupon later.
        client_secret = None
        
    return booking, client_secret

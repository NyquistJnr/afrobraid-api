import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, and_, case, cast, func, literal, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql import Select, exists

from app.modules.bookings.enums import BookingStatus
from app.modules.bookings.models import Booking
from app.modules.braiders.availability.models import (
    AvailabilityExceptionType,
    BraiderAvailabilityException,
    BraiderWeeklyAvailability,
    DayOfWeek,
)
from app.modules.braiders.models import BraiderOnboardingStatus, BraiderProfile
from app.modules.braiders.offerings.models import BraiderStyle
from app.modules.braiders.portfolio.models import PortfolioImage
from app.modules.braiders.service_location.models import BraiderServiceLocation
from app.modules.styles.models import AddOn, Style, StyleVariation
from app.modules.users.models import User, UserType

# Demand signal for "trending" - a braider committed to (not just started
# paying for, and not cancelled/disputed/no-showed) counts as real demand.
_TRENDING_BOOKING_STATUSES = (
    BookingStatus.CONFIRMED,
    BookingStatus.IN_PROGRESS,
    BookingStatus.COMPLETED,
)

# Meters, per Postgres earthdistance's `earth_distance()`/`ll_to_earth()`.
_METERS_PER_KM = 1000

_ISODOW_TO_DAY_OF_WEEK = {
    1: DayOfWeek.MONDAY,
    2: DayOfWeek.TUESDAY,
    3: DayOfWeek.WEDNESDAY,
    4: DayOfWeek.THURSDAY,
    5: DayOfWeek.FRIDAY,
    6: DayOfWeek.SATURDAY,
    7: DayOfWeek.SUNDAY,
}


def _distance_km_expr(lat: float, lng: float):
    return (
        func.earth_distance(
            func.ll_to_earth(lat, lng),
            func.ll_to_earth(BraiderServiceLocation.latitude, BraiderServiceLocation.longitude),
        )
        / _METERS_PER_KM
    )


def _available_in_range_filter(date_from: date, date_to: date):
    """True if the braider has at least one structurally-open day in the
    range: an active weekly window for that weekday (or an explicit
    CUSTOM_HOURS exception), not overridden by a CLOSED exception on that
    date. Doesn't account for a specific style's duration/buffer or
    min-notice - `/braiders/{id}/availability/slots` remains the source of
    truth for actual bookable times; this is a coarse browse-time filter."""
    day_series = (
        func.generate_series(cast(date_from, Date), cast(date_to, Date), text("interval '1 day'"))
        .table_valued("day")
        .render_derived()
    )

    weekday_expr = cast(
        case(
            *[
                (func.extract("isodow", day_series.c.day) == isodow, dow.value)
                for isodow, dow in _ISODOW_TO_DAY_OF_WEEK.items()
            ]
        ),
        BraiderWeeklyAvailability.day_of_week.type,
    )

    has_weekly = exists(
        select(1)
        .select_from(BraiderWeeklyAvailability)
        .where(
            BraiderWeeklyAvailability.braider_id == BraiderProfile.id,
            BraiderWeeklyAvailability.is_active.is_(True),
            BraiderWeeklyAvailability.day_of_week == weekday_expr,
        )
        .correlate(BraiderProfile, day_series)
    )
    has_custom = exists(
        select(1)
        .select_from(BraiderAvailabilityException)
        .where(
            BraiderAvailabilityException.braider_id == BraiderProfile.id,
            BraiderAvailabilityException.date == day_series.c.day,
            BraiderAvailabilityException.exception_type == AvailabilityExceptionType.CUSTOM_HOURS,
        )
        .correlate(BraiderProfile, day_series)
    )
    is_closed = exists(
        select(1)
        .select_from(BraiderAvailabilityException)
        .where(
            BraiderAvailabilityException.braider_id == BraiderProfile.id,
            BraiderAvailabilityException.date == day_series.c.day,
            BraiderAvailabilityException.exception_type == AvailabilityExceptionType.CLOSED,
        )
        .correlate(BraiderProfile, day_series)
    )

    return exists(select(1).select_from(day_series).where(or_(has_weekly, has_custom), ~is_closed))


# Every onboarding step, including PAYMENT_SETUP - a braider can't be
# publicly listed until they can actually get paid.
_REQUIRED_ONBOARDING_FIELDS = (
    BraiderOnboardingStatus.business_info_completed_at,
    BraiderOnboardingStatus.phone_verification_completed_at,
    BraiderOnboardingStatus.veriff_completed_at,
    BraiderOnboardingStatus.service_type_completed_at,
    BraiderOnboardingStatus.portfolio_completed_at,
    BraiderOnboardingStatus.service_location_completed_at,
    BraiderOnboardingStatus.availability_completed_at,
    BraiderOnboardingStatus.payment_setup_completed_at,
)


def _visibility_filters():
    return (
        User.user_type == UserType.BRAIDER,
        User.is_active.is_(True),
        *[field.is_not(None) for field in _REQUIRED_ONBOARDING_FIELDS],
    )


def _price_range_filter(min_amount: Decimal | None, max_amount: Decimal | None):
    """True if the braider has at least one active style priced within the
    given bounds. Uses its own aliased BraiderStyle so it doesn't collide
    with the style_id join in build_search_stmt."""
    priced_style = aliased(BraiderStyle)
    conditions = [
        priced_style.braider_id == BraiderProfile.id,
        priced_style.is_active.is_(True),
    ]
    if min_amount is not None:
        conditions.append(priced_style.base_price >= min_amount)
    if max_amount is not None:
        conditions.append(priced_style.base_price <= max_amount)
    return exists(select(1).select_from(priced_style).where(*conditions))


def build_search_stmt(
    *,
    lat: float | None,
    lng: float | None,
    radius_km: float | None,
    style_id: uuid.UUID | None,
    search: str | None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    min_rate: Decimal | None = None,
    max_rate: Decimal | None = None,
    country_code: str | None = None,
    is_mobile: bool | None = None,
) -> Select:
    """Row shape is (BraiderProfile, BraiderServiceLocation | None, distance_km | None)
    plus (BraiderStyle, Style) appended when `style_id` is given - callers must
    branch on the same `style_id` they passed in to know which shape to expect.
    """
    distance_expr = (
        _distance_km_expr(lat, lng) if lat is not None and lng is not None else literal(None)
    )
    entities: list = [BraiderProfile, BraiderServiceLocation, distance_expr.label("distance_km")]
    if style_id is not None:
        entities += [BraiderStyle, Style]

    stmt = (
        select(*entities)
        .join(User, User.id == BraiderProfile.user_id)
        .join(BraiderOnboardingStatus, BraiderOnboardingStatus.user_id == User.id)
        .outerjoin(BraiderServiceLocation, BraiderServiceLocation.braider_id == BraiderProfile.id)
        .where(*_visibility_filters())
    )

    if style_id is not None:
        stmt = stmt.join(
            BraiderStyle,
            and_(
                BraiderStyle.braider_id == BraiderProfile.id,
                BraiderStyle.style_id == style_id,
                BraiderStyle.is_active.is_(True),
            ),
        ).join(Style, Style.id == BraiderStyle.style_id)

    if search:
        stmt = stmt.where(BraiderProfile.business_name.ilike(f"%{search}%"))

    if date_from is not None and date_to is not None:
        stmt = stmt.where(_available_in_range_filter(date_from, date_to))

    if min_amount is not None or max_amount is not None:
        stmt = stmt.where(_price_range_filter(min_amount, max_amount))

    if min_rate is not None:
        stmt = stmt.where(BraiderProfile.average_rating >= min_rate)
    if max_rate is not None:
        stmt = stmt.where(BraiderProfile.average_rating <= max_rate)

    if country_code:
        stmt = stmt.where(BraiderServiceLocation.country == country_code)

    if is_mobile is not None:
        stmt = stmt.where(BraiderServiceLocation.offers_mobile.is_(is_mobile))

    if lat is not None and lng is not None:
        stmt = stmt.where(
            BraiderServiceLocation.latitude.is_not(None),
            BraiderServiceLocation.longitude.is_not(None),
        )
        if radius_km is not None:
            stmt = stmt.where(
                func.earth_box(func.ll_to_earth(lat, lng), radius_km * _METERS_PER_KM).op("@>")(
                    func.ll_to_earth(
                        BraiderServiceLocation.latitude, BraiderServiceLocation.longitude
                    )
                )
            )
        stmt = stmt.order_by(distance_expr)
    else:
        stmt = stmt.order_by(BraiderProfile.business_name)

    return stmt


def _browse_stmt(
    *,
    lat: float | None,
    lng: float | None,
    radius_km: float | None,
    country_code: str | None,
) -> Select:
    """Shared shape for the curated braider lists (new/top-rated/trending/
    recommended): same row shape and location scoping as `build_search_stmt`
    minus the style/price/date/search filters those don't need. Callers
    still need to add their own ORDER BY - distance is only meaningful when
    lat/lng are given, otherwise callers rank by their own criterion."""
    distance_expr = (
        _distance_km_expr(lat, lng) if lat is not None and lng is not None else literal(None)
    )
    stmt = (
        select(BraiderProfile, BraiderServiceLocation, distance_expr.label("distance_km"))
        .join(User, User.id == BraiderProfile.user_id)
        .join(BraiderOnboardingStatus, BraiderOnboardingStatus.user_id == User.id)
        .outerjoin(BraiderServiceLocation, BraiderServiceLocation.braider_id == BraiderProfile.id)
        .where(*_visibility_filters())
    )

    if country_code:
        stmt = stmt.where(BraiderServiceLocation.country == country_code)

    if lat is not None and lng is not None:
        stmt = stmt.where(
            BraiderServiceLocation.latitude.is_not(None),
            BraiderServiceLocation.longitude.is_not(None),
        )
        if radius_km is not None:
            stmt = stmt.where(
                func.earth_box(func.ll_to_earth(lat, lng), radius_km * _METERS_PER_KM).op("@>")(
                    func.ll_to_earth(
                        BraiderServiceLocation.latitude, BraiderServiceLocation.longitude
                    )
                )
            )

    return stmt


def build_new_braiders_stmt(
    *,
    since: datetime,
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float | None = None,
    country_code: str | None = None,
) -> Select:
    """Braiders whose onboarding (i.e. public visibility) completed on or
    after `since`. Ordered newest-first."""
    stmt = _browse_stmt(lat=lat, lng=lng, radius_km=radius_km, country_code=country_code)
    return stmt.where(BraiderOnboardingStatus.completed_at >= since).order_by(
        BraiderOnboardingStatus.completed_at.desc()
    )


# Minimum sample size before "top rated" ranking kicks in - low enough that
# an early-stage catalog (most braiders with just 1-2 reviews so far) still
# populates this list, while still filtering out completely unrated braiders.
# Raise this as review volume grows platform-wide.
_TOP_RATED_MIN_RATING_COUNT = 1


def build_top_rated_stmt(
    *,
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float | None = None,
    country_code: str | None = None,
) -> Select:
    stmt = _browse_stmt(lat=lat, lng=lng, radius_km=radius_km, country_code=country_code)
    return stmt.where(
        BraiderProfile.average_rating.is_not(None),
        BraiderProfile.rating_count >= _TOP_RATED_MIN_RATING_COUNT,
    ).order_by(BraiderProfile.average_rating.desc(), BraiderProfile.rating_count.desc())


def build_trending_stmt(
    *,
    since: datetime,
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float | None = None,
    country_code: str | None = None,
) -> Select:
    """Ranked by recent booking volume (bookings created since `since` in a
    committed/completed state - see `_TRENDING_BOOKING_STATUSES`), scoped to
    a country or a lat/lng radius. Callers must supply at least one of those
    scopes - "trending" is inherently relative to a place."""
    recent_booking_count = (
        select(func.count(Booking.id))
        .where(
            Booking.braider_id == BraiderProfile.id,
            Booking.created_at >= since,
            Booking.status.in_(_TRENDING_BOOKING_STATUSES),
        )
        .correlate(BraiderProfile)
        .scalar_subquery()
    )
    stmt = _browse_stmt(lat=lat, lng=lng, radius_km=radius_km, country_code=country_code)
    return (
        stmt.add_columns(recent_booking_count.label("recent_booking_count"))
        .where(recent_booking_count > 0)
        .order_by(recent_booking_count.desc(), BraiderProfile.average_rating.desc().nulls_last())
    )


# Flat bump applied to a braider's rating-based score if they're still within
# the "new braider" window (see build_new_braiders_stmt) - blends fresh
# braiders into the ranking instead of letting established, higher-volume
# ratings always crowd them out.
_RECOMMENDED_NEW_BRAIDER_BOOST = Decimal("0.5")


def build_recommended_stmt(
    *,
    new_since: datetime,
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float | None = None,
    country_code: str | None = None,
) -> Select:
    """No personalization signal yet (no purchase/browsing history feeding
    this): ranks by rating, with a boost for recently-onboarded braiders so
    the list isn't just a copy of top-rated. Swappable later for a real
    per-customer signal without changing the endpoint contract."""
    score = func.coalesce(BraiderProfile.average_rating, 0) + case(
        (BraiderOnboardingStatus.completed_at >= new_since, _RECOMMENDED_NEW_BRAIDER_BOOST),
        else_=0,
    )
    stmt = _browse_stmt(lat=lat, lng=lng, radius_km=radius_km, country_code=country_code)
    return stmt.order_by(score.desc(), BraiderProfile.rating_count.desc())


async def get_visible_profile_by_id(
    db: AsyncSession, braider_id: uuid.UUID
) -> BraiderProfile | None:
    stmt = (
        select(BraiderProfile)
        .join(User, User.id == BraiderProfile.user_id)
        .join(BraiderOnboardingStatus, BraiderOnboardingStatus.user_id == User.id)
        .where(BraiderProfile.id == braider_id, *_visibility_filters())
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_cover_photos(
    db: AsyncSession, braider_ids: list[uuid.UUID]
) -> dict[uuid.UUID, PortfolioImage]:
    """First (lowest-position) portfolio image per braider, for search result cards."""
    if not braider_ids:
        return {}
    result = await db.execute(
        select(PortfolioImage)
        .where(PortfolioImage.braider_id.in_(braider_ids))
        .order_by(PortfolioImage.braider_id, PortfolioImage.position)
    )
    covers: dict[uuid.UUID, PortfolioImage] = {}
    for image in result.scalars().all():
        covers.setdefault(image.braider_id, image)
    return covers


async def list_offered_styles(
    db: AsyncSession, braider_id: uuid.UUID
) -> list[tuple[BraiderStyle, Style]]:
    stmt = (
        select(BraiderStyle, Style)
        .join(Style, Style.id == BraiderStyle.style_id)
        .where(BraiderStyle.braider_id == braider_id, BraiderStyle.is_active.is_(True))
        .order_by(Style.name_en)
    )
    result = await db.execute(stmt)
    return [(row.BraiderStyle, row.Style) for row in result.all()]


async def list_offered_styles_for_braiders(
    db: AsyncSession, braider_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[tuple[BraiderStyle, Style]]]:
    """Batched menu lookup for a page of search results - avoids one query per
    braider card."""
    if not braider_ids:
        return {}
    stmt = (
        select(BraiderStyle, Style)
        .join(Style, Style.id == BraiderStyle.style_id)
        .where(BraiderStyle.braider_id.in_(braider_ids), BraiderStyle.is_active.is_(True))
        .order_by(BraiderStyle.braider_id, Style.name_en)
    )
    result = await db.execute(stmt)
    by_braider: dict[uuid.UUID, list[tuple[BraiderStyle, Style]]] = {}
    for row in result.all():
        by_braider.setdefault(row.BraiderStyle.braider_id, []).append((row.BraiderStyle, row.Style))
    return by_braider


async def get_style_variations_by_ids(
    db: AsyncSession, variation_ids: list[uuid.UUID]
) -> dict[uuid.UUID, StyleVariation]:
    if not variation_ids:
        return {}
    result = await db.execute(select(StyleVariation).where(StyleVariation.id.in_(variation_ids)))
    return {v.id: v for v in result.scalars().all()}


async def get_addons_by_ids(db: AsyncSession, addon_ids: list[uuid.UUID]) -> dict[uuid.UUID, AddOn]:
    if not addon_ids:
        return {}
    result = await db.execute(select(AddOn).where(AddOn.id.in_(addon_ids)))
    return {a.id: a for a in result.scalars().all()}

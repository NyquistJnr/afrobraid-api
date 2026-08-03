import uuid
from datetime import date

from sqlalchemy import Date, and_, case, cast, func, literal, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select, exists

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


def _visibility_filters():
    return (
        User.user_type == UserType.BRAIDER,
        User.is_active.is_(True),
        BraiderOnboardingStatus.completed_at.is_not(None),
    )


def build_search_stmt(
    *,
    lat: float | None,
    lng: float | None,
    radius_km: float | None,
    style_id: uuid.UUID | None,
    search: str | None,
    date_from: date | None = None,
    date_to: date | None = None,
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

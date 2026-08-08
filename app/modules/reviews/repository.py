import uuid
from decimal import Decimal

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginationParams, paginate
from app.modules.bookings.enums import BookingStatus
from app.modules.bookings.models import Booking
from app.modules.braiders.models import BraiderProfile
from app.modules.reviews.models import Review, ReviewStatus

# A booking in any of these statuses never reached a successful payment, so
# it doesn't grant review eligibility - every other status implies at least
# one payment (deposit or full) succeeded.
_INELIGIBLE_BOOKING_STATUSES = frozenset(
    {BookingStatus.PENDING_PAYMENT, BookingStatus.CANCELLED_NO_PAYMENT, BookingStatus.EXPIRED}
)


async def get_by_customer_and_braider(
    db: AsyncSession, customer_id: uuid.UUID, braider_id: uuid.UUID
) -> Review | None:
    result = await db.execute(
        select(Review).where(Review.customer_id == customer_id, Review.braider_id == braider_id)
    )
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, review_id: uuid.UUID) -> Review | None:
    return await db.get(Review, review_id)


async def has_eligible_booking(db: AsyncSession, customer_id: uuid.UUID, braider_id: uuid.UUID) -> bool:
    stmt = select(
        exists().where(
            Booking.customer_id == customer_id,
            Booking.braider_id == braider_id,
            Booking.status.not_in(_INELIGIBLE_BOOKING_STATUSES),
        )
    )
    return bool(await db.scalar(stmt))


async def create_review(
    db: AsyncSession, *, customer_id: uuid.UUID, braider_id: uuid.UUID, rating: int
) -> Review:
    review = Review(customer_id=customer_id, braider_id=braider_id, rating=rating)
    db.add(review)
    await db.flush()
    return review


async def list_approved_for_braider(
    db: AsyncSession, braider_id: uuid.UUID, *, params: PaginationParams
) -> tuple[list[Review], object]:
    stmt = (
        select(Review)
        .where(Review.braider_id == braider_id, Review.status == ReviewStatus.APPROVED)
        .order_by(Review.updated_at.desc())
    )
    return await paginate(db, stmt, params)


async def list_for_admin(
    db: AsyncSession, *, params: PaginationParams, status: ReviewStatus | None = None
) -> tuple[list[Review], object]:
    stmt = select(Review)
    if status is not None:
        stmt = stmt.where(Review.status == status)
    stmt = stmt.order_by(Review.created_at)
    return await paginate(db, stmt, params)


async def recompute_braider_rating(db: AsyncSession, braider_id: uuid.UUID) -> None:
    """Recomputes and stores BraiderProfile.average_rating/rating_count from
    every non-REJECTED review - called after any write that could change the
    aggregate (new/updated rating, or an admin approve/reject)."""
    result = await db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.braider_id == braider_id, Review.status != ReviewStatus.REJECTED
        )
    )
    average, count = result.one()
    profile = await db.get(BraiderProfile, braider_id)
    if profile is None:
        return
    profile.average_rating = Decimal(str(round(float(average), 2))) if average is not None else None
    profile.rating_count = count or 0

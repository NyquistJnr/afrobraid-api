import enum
import uuid
from datetime import date as date_
from datetime import datetime, time

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DayOfWeek(str, enum.Enum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


class AvailabilityExceptionType(str, enum.Enum):
    CLOSED = "CLOSED"
    CUSTOM_HOURS = "CUSTOM_HOURS"


class BraiderAvailabilitySettings(Base):
    __tablename__ = "braider_availability_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    braider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("braider_profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # IANA zone name (e.g. "Africa/Lagos") - weekly windows/exceptions are
    # stored as local wall-clock times and only mean something relative to
    # this, converted via zoneinfo so DST shifts are handled correctly.
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    min_notice_hours: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    max_advance_days: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    buffer_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BraiderWeeklyAvailability(Base):
    __tablename__ = "braider_weekly_availability"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_weekly_availability_end_after_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    braider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("braider_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[DayOfWeek] = mapped_column(
        Enum(DayOfWeek, name="day_of_week"), nullable=False
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BraiderAvailabilityException(Base):
    __tablename__ = "braider_availability_exceptions"
    __table_args__ = (
        CheckConstraint(
            "(exception_type = 'CLOSED' AND start_time IS NULL AND end_time IS NULL) OR "
            "(exception_type = 'CUSTOM_HOURS' AND start_time IS NOT NULL "
            "AND end_time IS NOT NULL AND end_time > start_time)",
            name="ck_availability_exception_times_match_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    braider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("braider_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date_] = mapped_column(Date, nullable=False)
    exception_type: Mapped[AvailabilityExceptionType] = mapped_column(
        Enum(AvailabilityExceptionType, name="availability_exception_type"), nullable=False
    )
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"
    PREFER_NOT_TO_SAY = "PREFER_NOT_TO_SAY"


class BioSource(str, enum.Enum):
    HUMAN = "HUMAN"
    MACHINE = "MACHINE"
    PENDING = "PENDING"
    FAILED = "FAILED"


class OnboardingStep(str, enum.Enum):
    BUSINESS_INFO = "BUSINESS_INFO"
    PHONE_VERIFICATION = "PHONE_VERIFICATION"
    VERIFF = "VERIFF"
    SERVICE_TYPE = "SERVICE_TYPE"
    PORTFOLIO = "PORTFOLIO"
    SERVICE_LOCATION = "SERVICE_LOCATION"
    AVAILABILITY = "AVAILABILITY"
    PAYMENT_SETUP = "PAYMENT_SETUP"
    COMPLETED = "COMPLETED"


class BraiderProfile(Base):
    __tablename__ = "braider_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    business_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    logo_object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bio_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio_de: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio_en_source: Mapped[BioSource | None] = mapped_column(
        Enum(BioSource, name="bio_source"), nullable=True
    )
    bio_de_source: Mapped[BioSource | None] = mapped_column(
        Enum(BioSource, name="bio_source"), nullable=True
    )
    bio_fr_source: Mapped[BioSource | None] = mapped_column(
        Enum(BioSource, name="bio_source"), nullable=True
    )
    gender: Mapped[Gender | None] = mapped_column(Enum(Gender, name="gender"), nullable=True)
    # Cached aggregate over app.modules.reviews.models.Review, recomputed by
    # reviews.repository.recompute_braider_rating on every rating change -
    # reading this avoids an AVG()/COUNT() join on every search result row.
    average_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BraiderOnboardingStatus(Base):
    __tablename__ = "braider_onboarding_statuses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    current_step: Mapped[OnboardingStep] = mapped_column(
        Enum(OnboardingStep, name="onboarding_step"),
        default=OnboardingStep.BUSINESS_INFO,
        nullable=False,
    )
    business_info_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    phone_verification_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    veriff_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    service_type_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    portfolio_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    service_location_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    availability_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payment_setup_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

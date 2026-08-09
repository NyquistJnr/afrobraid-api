import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.contact.enums import ContactPlatform, ContactPurpose


class ContactSubmission(Base):
    """A message sent through the public Contact Us form, from either app."""

    __tablename__ = "contact_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[ContactPlatform] = mapped_column(
        Enum(ContactPlatform, name="contact_platform"), nullable=False, index=True
    )
    purpose: Mapped[ContactPurpose] = mapped_column(
        Enum(ContactPurpose, name="contact_purpose"),
        nullable=False,
        default=ContactPurpose.GENERAL,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

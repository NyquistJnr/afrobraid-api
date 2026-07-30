import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.braiders.availability.models import AvailabilityExceptionType, DayOfWeek


class AvailabilitySettingsResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "timezone": "Africa/Lagos",
                    "min_notice_hours": 2,
                    "max_advance_days": 60,
                    "buffer_minutes": 15,
                }
            ]
        }
    )

    timezone: str
    min_notice_hours: int
    max_advance_days: int
    buffer_minutes: int


class AvailabilitySettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"timezone": "Africa/Lagos", "buffer_minutes": 15}]}
    )

    timezone: str | None = Field(
        default=None,
        description='IANA timezone name, e.g. "Africa/Lagos" - anchors how your weekly '
        "hours and exceptions are interpreted.",
    )
    min_notice_hours: int | None = Field(
        default=None, ge=0, description="How many hours in advance a client must book."
    )
    max_advance_days: int | None = Field(
        default=None, gt=0, description="How many days ahead clients can see open slots."
    )
    buffer_minutes: int | None = Field(
        default=None, ge=0, description="Gap enforced between consecutive bookable slots."
    )


class WeeklyWindowCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"day_of_week": "MONDAY", "start_time": "09:00", "end_time": "17:00"}]
        }
    )

    day_of_week: DayOfWeek
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _end_after_start(self) -> "WeeklyWindowCreateRequest":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class WeeklyWindowUpdateRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"is_active": False}]})

    start_time: time | None = None
    end_time: time | None = None
    is_active: bool | None = None


class WeeklyWindowResponse(BaseModel):
    id: uuid.UUID
    day_of_week: DayOfWeek
    start_time: time
    end_time: time
    is_active: bool


class AvailabilityExceptionCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"date": "2026-12-25", "exception_type": "CLOSED", "reason": "Public holiday"},
                {
                    "date": "2026-12-24",
                    "exception_type": "CUSTOM_HOURS",
                    "start_time": "09:00",
                    "end_time": "13:00",
                },
            ]
        }
    )

    date: date
    exception_type: AvailabilityExceptionType
    start_time: time | None = None
    end_time: time | None = None
    reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _times_match_type(self) -> "AvailabilityExceptionCreateRequest":
        if self.exception_type == AvailabilityExceptionType.CLOSED:
            if self.start_time is not None or self.end_time is not None:
                raise ValueError("A CLOSED exception can't have start_time/end_time set.")
        else:
            if self.start_time is None or self.end_time is None:
                raise ValueError(
                    "A CUSTOM_HOURS exception requires both start_time and end_time."
                )
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be after start_time")
        return self


class AvailabilityExceptionResponse(BaseModel):
    id: uuid.UUID
    date: date
    exception_type: AvailabilityExceptionType
    start_time: time | None
    end_time: time | None
    reason: str | None


class AvailableSlotResponse(BaseModel):
    start_at: datetime
    end_at: datetime

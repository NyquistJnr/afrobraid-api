import uuid
import zoneinfo
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AvailabilityExceptionNotFoundError,
    AvailabilitySettingsNotConfiguredError,
    BraiderStyleDurationMissingError,
    BraiderStyleNotFoundError,
    InvalidAvailabilityWindowTimesError,
    InvalidTimezoneError,
    OverlappingAvailabilityExceptionError,
    OverlappingAvailabilityWindowError,
    WeeklyWindowNotFoundError,
)
from app.modules.braiders import repository as braiders_repo
from app.modules.braiders.availability import repository as availability_repo
from app.modules.braiders.availability.models import (
    AvailabilityExceptionType,
    BraiderAvailabilityException,
    BraiderAvailabilitySettings,
    BraiderWeeklyAvailability,
    DayOfWeek,
)
from app.modules.braiders.availability.schemas import (
    AvailabilityExceptionCreateRequest,
    AvailabilityExceptionResponse,
    AvailabilitySettingsResponse,
    AvailabilitySettingsUpdateRequest,
    AvailableSlotResponse,
    WeeklyWindowCreateRequest,
    WeeklyWindowResponse,
    WeeklyWindowUpdateRequest,
)
from app.modules.braiders.completion import mark_step_complete
from app.modules.braiders.models import BraiderProfile, OnboardingStep
from app.modules.braiders.offerings import repository as offerings_repo

_WEEKDAY_TO_DAY_OF_WEEK = [
    DayOfWeek.MONDAY,
    DayOfWeek.TUESDAY,
    DayOfWeek.WEDNESDAY,
    DayOfWeek.THURSDAY,
    DayOfWeek.FRIDAY,
    DayOfWeek.SATURDAY,
    DayOfWeek.SUNDAY,
]


async def _get_or_create_profile(db: AsyncSession, user_id: uuid.UUID) -> BraiderProfile:
    profile = await braiders_repo.get_profile_by_user_id(db, user_id)
    if profile is None:
        profile = await braiders_repo.create_profile_for_user(db, user_id)
    return profile


async def _get_or_create_settings(
    db: AsyncSession, braider_id: uuid.UUID
) -> BraiderAvailabilitySettings:
    settings = await availability_repo.get_settings_by_braider_id(db, braider_id)
    if settings is None:
        settings = await availability_repo.create_settings_for_braider(db, braider_id)
    return settings


def _settings_to_response(settings: BraiderAvailabilitySettings) -> AvailabilitySettingsResponse:
    return AvailabilitySettingsResponse(
        timezone=settings.timezone,
        min_notice_hours=settings.min_notice_hours,
        max_advance_days=settings.max_advance_days,
        buffer_minutes=settings.buffer_minutes,
    )


def _window_to_response(window: BraiderWeeklyAvailability) -> WeeklyWindowResponse:
    return WeeklyWindowResponse(
        id=window.id,
        day_of_week=window.day_of_week,
        start_time=window.start_time,
        end_time=window.end_time,
        is_active=window.is_active,
    )


def _exception_to_response(
    exception: BraiderAvailabilityException,
) -> AvailabilityExceptionResponse:
    return AvailabilityExceptionResponse(
        id=exception.id,
        date=exception.date,
        exception_type=exception.exception_type,
        start_time=exception.start_time,
        end_time=exception.end_time,
        reason=exception.reason,
    )


async def get_settings(db: AsyncSession, user_id: uuid.UUID) -> AvailabilitySettingsResponse:
    profile = await _get_or_create_profile(db, user_id)
    settings = await _get_or_create_settings(db, profile.id)
    await db.commit()
    return _settings_to_response(settings)


async def update_settings(
    db: AsyncSession, user_id: uuid.UUID, *, data: AvailabilitySettingsUpdateRequest
) -> AvailabilitySettingsResponse:
    profile = await _get_or_create_profile(db, user_id)
    settings = await _get_or_create_settings(db, profile.id)

    updates = data.model_dump(exclude_unset=True)
    if updates.get("timezone") is not None and updates["timezone"] not in zoneinfo.available_timezones():
        raise InvalidTimezoneError()
    for field, value in updates.items():
        setattr(settings, field, value)

    await db.commit()
    return _settings_to_response(settings)


def _windows_overlap(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end


async def list_weekly_windows(
    db: AsyncSession, user_id: uuid.UUID
) -> list[WeeklyWindowResponse]:
    profile = await _get_or_create_profile(db, user_id)
    windows = await availability_repo.list_weekly_windows(db, profile.id)
    await db.commit()
    return [_window_to_response(w) for w in windows]


async def create_weekly_window(
    db: AsyncSession, user_id: uuid.UUID, *, data: WeeklyWindowCreateRequest
) -> WeeklyWindowResponse:
    profile = await _get_or_create_profile(db, user_id)

    existing = await availability_repo.list_weekly_windows_for_day(
        db, profile.id, data.day_of_week
    )
    for other in existing:
        if _windows_overlap(data.start_time, data.end_time, other.start_time, other.end_time):
            raise OverlappingAvailabilityWindowError()

    window = await availability_repo.create_weekly_window(
        db,
        braider_id=profile.id,
        day_of_week=data.day_of_week,
        start_time=data.start_time,
        end_time=data.end_time,
    )

    # Creating the first weekly window is the concrete signal (mirroring how
    # adding a menu style completes SERVICE_TYPE) that this braider has
    # actually configured their schedule, not just an auto-created row with
    # defaults - so it's what completes this onboarding step.
    onboarding_status = await braiders_repo.get_onboarding_status_by_user_id(db, user_id)
    if onboarding_status is None:
        onboarding_status = await braiders_repo.create_onboarding_status_for_user(db, user_id)
    mark_step_complete(onboarding_status, OnboardingStep.AVAILABILITY)

    await db.commit()
    return _window_to_response(window)


async def update_weekly_window(
    db: AsyncSession,
    user_id: uuid.UUID,
    window_id: uuid.UUID,
    *,
    data: WeeklyWindowUpdateRequest,
) -> WeeklyWindowResponse:
    profile = await _get_or_create_profile(db, user_id)
    window = await availability_repo.get_weekly_window_by_id(db, window_id)
    if window is None or window.braider_id != profile.id:
        raise WeeklyWindowNotFoundError()

    updates = data.model_dump(exclude_unset=True)
    new_start = updates.get("start_time", window.start_time)
    new_end = updates.get("end_time", window.end_time)
    if new_end <= new_start:
        raise InvalidAvailabilityWindowTimesError()

    if "start_time" in updates or "end_time" in updates:
        others = await availability_repo.list_weekly_windows_for_day(
            db, profile.id, window.day_of_week
        )
        for other in others:
            if other.id == window.id:
                continue
            if _windows_overlap(new_start, new_end, other.start_time, other.end_time):
                raise OverlappingAvailabilityWindowError()

    for field, value in updates.items():
        setattr(window, field, value)

    await db.commit()
    return _window_to_response(window)


async def delete_weekly_window(db: AsyncSession, user_id: uuid.UUID, window_id: uuid.UUID) -> None:
    profile = await _get_or_create_profile(db, user_id)
    window = await availability_repo.get_weekly_window_by_id(db, window_id)
    if window is None or window.braider_id != profile.id:
        raise WeeklyWindowNotFoundError()

    await availability_repo.delete_weekly_window(db, window)
    await db.commit()


async def list_exceptions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[AvailabilityExceptionResponse]:
    profile = await _get_or_create_profile(db, user_id)
    exceptions = await availability_repo.list_exceptions(
        db, profile.id, date_from=date_from, date_to=date_to
    )
    await db.commit()
    return [_exception_to_response(e) for e in exceptions]


async def create_exception(
    db: AsyncSession, user_id: uuid.UUID, *, data: AvailabilityExceptionCreateRequest
) -> AvailabilityExceptionResponse:
    profile = await _get_or_create_profile(db, user_id)

    existing = await availability_repo.list_exceptions_for_date(db, profile.id, data.date)
    if existing:
        if data.exception_type == AvailabilityExceptionType.CLOSED or any(
            e.exception_type == AvailabilityExceptionType.CLOSED for e in existing
        ):
            # A date can't mix CLOSED with anything else.
            raise OverlappingAvailabilityExceptionError()
        for other in existing:
            if _windows_overlap(data.start_time, data.end_time, other.start_time, other.end_time):
                raise OverlappingAvailabilityExceptionError()

    exception = await availability_repo.create_exception(
        db,
        braider_id=profile.id,
        on_date=data.date,
        exception_type=data.exception_type,
        start_time=data.start_time,
        end_time=data.end_time,
        reason=data.reason,
    )
    await db.commit()
    return _exception_to_response(exception)


async def delete_exception(db: AsyncSession, user_id: uuid.UUID, exception_id: uuid.UUID) -> None:
    profile = await _get_or_create_profile(db, user_id)
    exception = await availability_repo.get_exception_by_id(db, exception_id)
    if exception is None or exception.braider_id != profile.id:
        raise AvailabilityExceptionNotFoundError()

    await availability_repo.delete_exception(db, exception)
    await db.commit()


async def compute_available_slots(
    db: AsyncSession,
    braider_id: uuid.UUID,
    style_id: uuid.UUID,
    *,
    date_from: date,
    date_to: date,
) -> list[AvailableSlotResponse]:
    settings = await availability_repo.get_settings_by_braider_id(db, braider_id)
    if settings is None:
        raise AvailabilitySettingsNotConfiguredError()

    braider_style = await offerings_repo.get_braider_style_by_style_id(db, braider_id, style_id)
    if braider_style is None or not braider_style.is_active:
        raise BraiderStyleNotFoundError()
    if braider_style.duration_minutes is None:
        raise BraiderStyleDurationMissingError()

    tz = zoneinfo.ZoneInfo(settings.timezone)
    duration = timedelta(minutes=braider_style.duration_minutes)
    step = duration + timedelta(minutes=settings.buffer_minutes)

    now_local = datetime.now(tz)
    earliest_start = now_local + timedelta(hours=settings.min_notice_hours)
    latest_date = now_local.date() + timedelta(days=settings.max_advance_days)

    range_start = max(date_from, now_local.date())
    range_end = min(date_to, latest_date)
    if range_start > range_end:
        return []

    weekly_windows_by_day: dict[DayOfWeek, list[BraiderWeeklyAvailability]] = {}
    slots: list[AvailableSlotResponse] = []

    current = range_start
    while current <= range_end:
        day_exceptions = await availability_repo.list_exceptions_for_date(db, braider_id, current)
        if any(e.exception_type == AvailabilityExceptionType.CLOSED for e in day_exceptions):
            current += timedelta(days=1)
            continue

        custom_windows = [
            (e.start_time, e.end_time)
            for e in day_exceptions
            if e.exception_type == AvailabilityExceptionType.CUSTOM_HOURS
        ]
        if custom_windows:
            windows = custom_windows
        else:
            day_of_week = _WEEKDAY_TO_DAY_OF_WEEK[current.weekday()]
            if day_of_week not in weekly_windows_by_day:
                weekly_windows_by_day[day_of_week] = await availability_repo.list_weekly_windows_for_day(
                    db, braider_id, day_of_week, active_only=True
                )
            windows = [(w.start_time, w.end_time) for w in weekly_windows_by_day[day_of_week]]

        for start_t, end_t in windows:
            window_start = datetime.combine(current, start_t, tzinfo=tz)
            window_end = datetime.combine(current, end_t, tzinfo=tz)
            slot_start = window_start
            while slot_start + duration <= window_end:
                slot_end = slot_start + duration
                if slot_start >= earliest_start:
                    slots.append(
                        AvailableSlotResponse(
                            start_at=slot_start.astimezone(UTC),
                            end_at=slot_end.astimezone(UTC),
                        )
                    )
                slot_start += step

        current += timedelta(days=1)

    return slots

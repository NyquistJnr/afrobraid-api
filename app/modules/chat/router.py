import uuid

from arq import ArqRedis
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginatedData, PaginationParams
from app.core.queue import get_task_queue
from app.core.response import APIResponse
from app.modules.auth.dependencies import get_current_user
from app.modules.chat import service
from app.modules.chat.schemas import (
    ChatMessageCreateRequest,
    ChatMessageResponse,
    ChatReportCreateRequest,
    ChatReportResponse,
    ChatThreadResponse,
)
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.get(
    "/threads",
    response_model=APIResponse[PaginatedData[ChatThreadResponse]],
    summary="List your conversations",
    description="Every chat thread you're a participant in (as customer or braider), newest "
    "activity first.",
)
async def list_threads(
    params: PaginationParams = Depends(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedData[ChatThreadResponse]]:
    result = await service.list_my_threads(db, user_id=user.id, params=params)
    return APIResponse(data=result)


@router.get(
    "/bookings/{booking_id}/thread",
    response_model=APIResponse[ChatThreadResponse],
    summary="Get (or start) the conversation for a booking",
    description="Creates the thread the first time either side opens it. Only available once "
    "the booking's deposit (or full payment) has succeeded - stays available even if the "
    "booking is later cancelled, so a dispute can still be discussed.",
)
async def get_thread_for_booking(
    booking_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ChatThreadResponse]:
    result = await service.get_or_create_thread_for_booking(db, booking_id=booking_id, user_id=user.id)
    return APIResponse(data=result)


@router.get(
    "/threads/{thread_id}/messages",
    response_model=APIResponse[PaginatedData[ChatMessageResponse]],
    summary="List messages in a conversation",
    description="Newest first (page 1 = most recent). A FLAGGED message has `body: null` - show "
    "`violation_notice` instead.",
)
async def list_messages(
    thread_id: uuid.UUID,
    request: Request,
    params: PaginationParams = Depends(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedData[ChatMessageResponse]]:
    result = await service.list_messages(
        db, thread_id=thread_id, user_id=user.id, params=params, locale=_locale(request)
    )
    return APIResponse(data=result)


@router.post(
    "/threads/{thread_id}/messages",
    response_model=APIResponse[ChatMessageResponse],
    summary="Send a message",
    description="Messages that look like they're sharing contact details or payment/account "
    "info are withheld automatically - the response still comes back successfully, but with "
    "`status: FLAGGED`, `body: null`, and a `violation_notice` explaining why. Set your chat "
    "language via `PATCH /api/v1/users/me` (`chat_locale`) so messages translate automatically "
    "when it differs from the other participant's.",
)
async def send_message(
    thread_id: uuid.UUID,
    payload: ChatMessageCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_task_queue),
) -> APIResponse[ChatMessageResponse]:
    result = await service.send_message(
        db,
        thread_id=thread_id,
        sender_id=user.id,
        data=payload,
        request_locale=_locale(request),
        queue=queue,
    )
    return APIResponse(data=result)


@router.post(
    "/threads/{thread_id}/read",
    response_model=APIResponse[ChatThreadResponse],
    summary="Mark a conversation as read",
)
async def mark_read(
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ChatThreadResponse]:
    result = await service.mark_read(db, thread_id=thread_id, user_id=user.id)
    return APIResponse(data=result)


@router.post(
    "/threads/{thread_id}/report",
    response_model=APIResponse[ChatReportResponse],
    summary="Report the other person in this conversation",
    description="Reports the other participant in this thread for abuse, spam, scam attempts, "
    "off-platform solicitation, etc. Reviewed by Afrobraid staff.",
)
async def report_participant(
    thread_id: uuid.UUID,
    payload: ChatReportCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ChatReportResponse]:
    result = await service.create_report(db, thread_id=thread_id, reporter_id=user.id, data=payload)
    return APIResponse(data=result)

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginatedData, PaginationParams
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.chat import service
from app.modules.chat.models import ChatReportStatus
from app.modules.chat.schemas import AdminChatReportResponse, AdminChatReportUpdateRequest
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/admin/chat/reports", tags=["Admin - Chat"])

_require_admin = require_roles(UserType.ADMIN)


@router.get(
    "",
    response_model=APIResponse[PaginatedData[AdminChatReportResponse]],
    summary="List chat reports for moderation",
    description="Defaults to `status=OPEN` - pass another `status` or omit the filter to browse all reports.",
)
async def list_reports(
    status_filter: ChatReportStatus | None = Query(default=ChatReportStatus.OPEN, alias="status"),
    params: PaginationParams = Depends(),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedData[AdminChatReportResponse]]:
    result = await service.list_admin_reports(db, params=params, status=status_filter)
    return APIResponse(data=result)


@router.patch(
    "/{report_id}",
    response_model=APIResponse[AdminChatReportResponse],
    summary="Update a chat report's status",
)
async def update_report(
    report_id: uuid.UUID,
    payload: AdminChatReportUpdateRequest,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AdminChatReportResponse]:
    result = await service.update_report(db, report_id=report_id, data=payload)
    return APIResponse(data=result)

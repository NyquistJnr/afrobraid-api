from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.bookings import service
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/admin/bookings", tags=["Admin - Bookings"])

_require_admin = require_roles(UserType.ADMIN)


@router.get(
    "/today-count",
    response_model=APIResponse[int],
    summary="Total bookings made today",
    description="No params. Counts every booking created today (UTC calendar day), regardless of status.",
)
async def get_bookings_today_count(
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[int]:
    result = await service.count_bookings_today(db)
    return APIResponse(data=result)

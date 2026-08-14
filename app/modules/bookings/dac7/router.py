from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import APIResponse
from app.modules.auth.dependencies import require_roles
from app.modules.bookings.dac7 import service
from app.modules.bookings.dac7.schemas import Dac7ReportResponse
from app.modules.users.models import User, UserType

router = APIRouter(prefix="/api/v1/admin/dac7", tags=["Admin - DAC7"])

_require_admin = require_roles(UserType.ADMIN)


@router.get(
    "/report",
    response_model=APIResponse[Dac7ReportResponse],
    summary="DAC7/PStTG quarterly reporting aggregation",
    description=(
        "Per (braider, country, currency): booking count, gross "
        "consideration (the braider's share), and platform fees withheld, "
        "for every COMPLETED/NO_SHOW booking whose appointment fell in "
        "the given quarter. A draft aggregation, not a submission-ready "
        "filing - see the response's `note`."
    ),
)
async def get_dac7_report(
    year: int = Query(..., ge=2020, le=2100),
    quarter: int = Query(..., ge=1, le=4),
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[Dac7ReportResponse]:
    result = await service.generate_report(db, year=year, quarter=quarter)
    return APIResponse(data=result)

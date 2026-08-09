from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import ip_rate_limiter
from app.core.response import APIResponse
from app.modules.contact import service
from app.modules.contact.schemas import ContactSubmissionRequest, ContactSubmissionResponse

router = APIRouter(prefix="/api/v1/contact", tags=["Contact"])


def _locale(request: Request) -> str:
    return getattr(request.state, "locale", "en")


@router.post(
    "",
    response_model=APIResponse[ContactSubmissionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Submit the Contact Us form",
    description="Public, no auth required.",
    dependencies=[Depends(ip_rate_limiter(key_prefix="contact", limit=5, window_seconds=3600))],
)
async def submit_contact_form(
    payload: ContactSubmissionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ContactSubmissionResponse]:
    result = await service.submit_contact_form(db, data=payload, locale=_locale(request))
    return APIResponse(data=result)

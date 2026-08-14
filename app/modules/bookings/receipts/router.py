from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ReceiptNotFoundError
from app.modules.bookings.receipts import repository as receipts_repo

router = APIRouter(prefix="/api/v1/receipts", tags=["Receipts"])


@router.get(
    "/{public_token}",
    response_class=HTMLResponse,
    summary="View a receipt",
    description=(
        "Public, no auth - the token itself is the credential (a random "
        "24-byte value, not a guessable id). Returns the exact HTML "
        "rendered at issuance time; it never changes, even if the "
        "booking's locale or the receipt template are updated later. A "
        "deliberate exception to the `APIResponse[T]` envelope - this is "
        "a document, not an API payload."
    ),
)
async def get_receipt(public_token: str, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    receipt = await receipts_repo.get_receipt_by_public_token(db, public_token)
    if receipt is None:
        raise ReceiptNotFoundError()
    return HTMLResponse(content=receipt.html)

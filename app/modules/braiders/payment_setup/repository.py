import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.braiders.payment_setup.models import StripeConnectAccount


async def get_by_braider_id(
    db: AsyncSession, braider_id: uuid.UUID
) -> StripeConnectAccount | None:
    result = await db.execute(
        select(StripeConnectAccount).where(StripeConnectAccount.braider_id == braider_id)
    )
    return result.scalar_one_or_none()


async def get_by_stripe_account_id(
    db: AsyncSession, stripe_account_id: str
) -> StripeConnectAccount | None:
    result = await db.execute(
        select(StripeConnectAccount).where(
            StripeConnectAccount.stripe_account_id == stripe_account_id
        )
    )
    return result.scalar_one_or_none()


async def create_for_braider(
    db: AsyncSession, *, braider_id: uuid.UUID, stripe_account_id: str
) -> StripeConnectAccount:
    account = StripeConnectAccount(braider_id=braider_id, stripe_account_id=stripe_account_id)
    db.add(account)
    await db.flush()
    return account

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.braiders.veriff.models import VeriffSession, VeriffSessionStatus


async def create_session_record(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    veriff_session_id: str,
    verification_url: str,
    status: VeriffSessionStatus,
) -> VeriffSession:
    session = VeriffSession(
        user_id=user_id,
        veriff_session_id=veriff_session_id,
        verification_url=verification_url,
        status=status,
    )
    db.add(session)
    await db.flush()
    return session


async def get_latest_session_by_user_id(
    db: AsyncSession, user_id: uuid.UUID
) -> VeriffSession | None:
    result = await db.execute(
        select(VeriffSession)
        .where(VeriffSession.user_id == user_id)
        .order_by(VeriffSession.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_session_by_veriff_id(
    db: AsyncSession, veriff_session_id: str
) -> VeriffSession | None:
    result = await db.execute(
        select(VeriffSession).where(VeriffSession.veriff_session_id == veriff_session_id)
    )
    return result.scalar_one_or_none()

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import OtpCode, OtpPurpose, RefreshToken


async def create_otp_code(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    code_hash: str,
    purpose: OtpPurpose,
    expire_minutes: int,
) -> OtpCode:
    otp = OtpCode(
        user_id=user_id,
        code_hash=code_hash,
        purpose=purpose,
        expires_at=datetime.now(UTC) + timedelta(minutes=expire_minutes),
    )
    db.add(otp)
    await db.flush()
    return otp


async def get_latest_active_otp(
    db: AsyncSession, *, user_id: uuid.UUID, purpose: OtpPurpose
) -> OtpCode | None:
    result = await db.execute(
        select(OtpCode)
        .where(
            OtpCode.user_id == user_id,
            OtpCode.purpose == purpose,
            OtpCode.consumed_at.is_(None),
        )
        .order_by(OtpCode.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def invalidate_active_otps(
    db: AsyncSession, *, user_id: uuid.UUID, purpose: OtpPurpose
) -> None:
    result = await db.execute(
        select(OtpCode).where(
            OtpCode.user_id == user_id,
            OtpCode.purpose == purpose,
            OtpCode.consumed_at.is_(None),
        )
    )
    now = datetime.now(UTC)
    for otp in result.scalars():
        otp.consumed_at = now
    await db.flush()


async def create_refresh_token(
    db: AsyncSession, *, user_id: uuid.UUID, token_hash: str, expire_days: int
) -> RefreshToken:
    token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=expire_days),
    )
    db.add(token)
    await db.flush()
    return token


async def get_refresh_token_by_hash(db: AsyncSession, token_hash: str) -> RefreshToken | None:
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    return result.scalar_one_or_none()


async def revoke_refresh_token(db: AsyncSession, token: RefreshToken) -> None:
    token.revoked_at = datetime.now(UTC)
    await db.flush()


async def revoke_all_refresh_tokens_for_user(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    now = datetime.now(UTC)
    for token in result.scalars():
        token.revoked_at = now
    await db.flush()

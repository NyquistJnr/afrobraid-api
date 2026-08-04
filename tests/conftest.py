from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis as redis_module
from app.core.database import AsyncSessionLocal, engine
from app.core.redis import get_redis_client
from app.main import app


class FakeArqPool:
    """Records enqueued jobs instead of touching Redis/arq during tests."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, dict]] = []

    async def enqueue_job(self, function: str, **kwargs) -> None:
        self.jobs.append((function, kwargs))

    def last_job_kwargs(self, function: str) -> dict:
        for name, kwargs in reversed(self.jobs):
            if name == function:
                return kwargs
        raise AssertionError(f"No job enqueued for {function!r}")


@pytest.fixture(autouse=True)
async def _clean_state() -> AsyncGenerator[None]:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE refresh_tokens, otp_codes, auth_identities, "
                "booking_calculation_addons, booking_calculations, "
                "braider_style_addons, braider_style_variations, braider_styles, "
                "portfolio_images, braider_service_locations, "
                "braider_availability_exceptions, braider_weekly_availability, "
                "braider_availability_settings, stripe_connect_accounts, "
                "platform_settings, "
                "addons, style_variations, "
                "stripe_webhook_events, booking_payments, booking_items, bookings, "
                "style_images, styles, style_categories, braider_onboarding_statuses, "
                "braider_profiles, users "
                "RESTART IDENTITY CASCADE"
            )
        )
    redis_client = get_redis_client()
    await redis_client.flushdb()
    await redis_client.aclose()

    yield

    # pytest-asyncio uses a fresh event loop per test by default, but the
    # SQLAlchemy engine and Redis connection pool are process-wide singletons
    # whose connections are bound to whichever loop created them. Dispose both
    # here — while this test's loop is still alive — so the next test (on a
    # new loop) opens fresh connections instead of reusing dead ones.
    await engine.dispose()
    await redis_module._pool.disconnect()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
def fake_queue() -> FakeArqPool:
    return FakeArqPool()


@pytest.fixture
async def client(fake_queue: FakeArqPool) -> AsyncGenerator[AsyncClient]:
    app.state.arq_pool = fake_queue
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

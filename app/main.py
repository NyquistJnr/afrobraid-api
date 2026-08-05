from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.i18n import LocaleMiddleware
from app.core.logging import configure_logging
from app.core.queue import create_arq_pool
from app.modules.auth.router import router as auth_router
from app.modules.bookings.braider_router import router as braider_bookings_router
from app.modules.bookings.calculations.router import router as booking_calculations_router
from app.modules.bookings.payments.webhook import router as stripe_payments_webhook_router
from app.modules.bookings.router import router as bookings_router
from app.modules.braiders.availability.router import (
    public_router as braider_availability_public_router,
)
from app.modules.braiders.availability.router import router as braider_availability_router
from app.modules.braiders.discovery.router import router as braider_discovery_router
from app.modules.braiders.offerings.router import router as braider_offerings_router
from app.modules.braiders.payment_setup.router import router as braider_payment_setup_router
from app.modules.braiders.payment_setup.webhook import router as stripe_webhook_router
from app.modules.braiders.phone_verification.router import router as phone_verification_router
from app.modules.braiders.portfolio.router import router as braider_portfolio_router
from app.modules.braiders.router import router as braiders_router
from app.modules.braiders.service_location.router import router as braider_service_location_router
from app.modules.braiders.veriff.router import router as veriff_router
from app.modules.braiders.veriff.webhook import router as veriff_webhook_router
from app.modules.media.router import router as media_router
from app.modules.platform_settings.router import router as platform_settings_router
from app.modules.styles.admin_router import router as styles_admin_router
from app.modules.styles.router import router as styles_router
from app.modules.users.router import router as users_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    app.state.arq_pool = await create_arq_pool()
    yield
    await app.state.arq_pool.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Afrobraid API",
        version="0.1.0",
        lifespan=lifespan,
        swagger_ui_parameters={
            "docExpansion": "none",  # all tags collapsed by default
            "defaultModelsExpandDepth": -1,  # hides the "Schemas" section entirely
        },
    )

    # Middlewares are applied outside-in in reverse of registration order,
    # so CORS is added last to stay the outermost layer.
    app.add_middleware(LocaleMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(braiders_router)
    app.include_router(phone_verification_router)
    app.include_router(veriff_router)
    app.include_router(veriff_webhook_router)
    app.include_router(media_router)
    app.include_router(platform_settings_router)
    app.include_router(styles_router)
    app.include_router(styles_admin_router)
    app.include_router(braider_offerings_router)
    app.include_router(braider_portfolio_router)
    app.include_router(braider_service_location_router)
    app.include_router(braider_availability_router)
    app.include_router(braider_availability_public_router)
    app.include_router(braider_discovery_router)
    app.include_router(braider_payment_setup_router)
    app.include_router(stripe_webhook_router)
    app.include_router(booking_calculations_router)
    app.include_router(bookings_router)
    app.include_router(braider_bookings_router)
    app.include_router(stripe_payments_webhook_router)

    @app.get("/health", tags=["Health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

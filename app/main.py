from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.i18n import LocaleMiddleware
from app.core.logging import configure_logging
from app.core.queue import create_arq_pool
from app.modules.auth.router import router as auth_router

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

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

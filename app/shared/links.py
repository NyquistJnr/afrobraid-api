from typing import Literal

from app.core.config import get_settings

settings = get_settings()

FrontendApp = Literal["customer", "braider", "admin"]


def _frontend_base_url(app: FrontendApp) -> str:
    app_url = {
        "customer": settings.customer_frontend_url,
        "braider": settings.braider_frontend_url,
        "admin": settings.admin_frontend_url,
    }[app]
    return (app_url or settings.frontend_url).rstrip("/")


def build_frontend_url(*, locale: str | None = None, path: str, app: FrontendApp = "customer") -> str:
    """A locale-prefixed deep-link into the web app, e.g.
    build_frontend_url(locale="fr", path="bookings/<id>", app="customer") ->
    "http://localhost:3000/fr/bookings/<id>".

    The locale segment is fixed at the moment the link is built (e.g. the
    language a booking was paid in, or a chat recipient's chat_locale) -
    unlike a notification's title/body text, which re-renders in whatever
    locale the reader is currently viewing the app in.
    """
    base_url = _frontend_base_url(app)
    normalized_path = path.lstrip("/")
    if locale is None:
        return f"{base_url}/{normalized_path}" if normalized_path else base_url
    return f"{base_url}/{locale}/{normalized_path}" if normalized_path else f"{base_url}/{locale}"


def build_customer_frontend_url(*, locale: str, path: str) -> str:
    return build_frontend_url(locale=locale, path=path, app="customer")


def build_braider_frontend_url(*, locale: str, path: str) -> str:
    return build_frontend_url(locale=locale, path=path, app="braider")


def build_admin_frontend_url(*, path: str) -> str:
    return build_frontend_url(path=path, app="admin")

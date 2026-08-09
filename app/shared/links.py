from app.core.config import get_settings

settings = get_settings()


def build_frontend_url(*, locale: str, path: str) -> str:
    """A locale-prefixed deep-link into the web app, e.g.
    build_frontend_url(locale="fr", path="bookings/<id>") ->
    "http://localhost:3000/fr/bookings/<id>".

    The locale segment is fixed at the moment the link is built (e.g. the
    language a booking was paid in, or a chat recipient's chat_locale) -
    unlike a notification's title/body text, which re-renders in whatever
    locale the reader is currently viewing the app in.
    """
    return f"{settings.frontend_url.rstrip('/')}/{locale}/{path.lstrip('/')}"

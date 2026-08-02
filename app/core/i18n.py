import json
from pathlib import Path
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from app.core.config import get_settings

settings = get_settings()

_LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"

_translations: dict[str, dict[str, str]] = {}


def _load_translations() -> None:
    for locale in settings.supported_locales_list:
        path = _LOCALES_DIR / f"{locale}.json"
        if path.exists():
            _translations[locale] = json.loads(path.read_text(encoding="utf-8"))


_load_translations()


def resolve_locale(accept_language: str | None, query_lang: str | None = None) -> str:
    supported = settings.supported_locales_list

    if query_lang:
        candidate = query_lang.strip().lower()[:2]
        if candidate in supported:
            return candidate

    if accept_language:
        for part in accept_language.split(","):
            code = part.split(";")[0].strip().lower()[:2]
            if code in supported:
                return code

    return settings.default_locale


def localize_field(entity: Any, field: str, locale: str) -> str | None:
    """Picks the best available `{field}_{locale}` value off `entity`.

    Falls back requested locale -> default locale -> first non-null supported
    locale, so display endpoints never have to expose per-locale nulls (e.g. a
    machine translation still pending) to the frontend.
    """
    order = [locale, settings.default_locale, *settings.supported_locales_list]
    seen: set[str] = set()
    for loc in order:
        if loc in seen:
            continue
        seen.add(loc)
        value = getattr(entity, f"{field}_{loc}", None)
        if value:
            return value
    return None


def t(key: str, locale: str, **kwargs: Any) -> str:
    locale_map = _translations.get(locale) or _translations.get(settings.default_locale, {})
    template = locale_map.get(key)
    if template is None:
        template = _translations.get(settings.default_locale, {}).get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template


class LocaleMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        locale = resolve_locale(
            accept_language=request.headers.get("accept-language"),
            query_lang=request.query_params.get("lang"),
        )
        request.state.locale = locale
        return await call_next(request)

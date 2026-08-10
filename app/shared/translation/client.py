import asyncio
import logging

import httpx

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("app.translation")

# DeepL accepts plain "EN" as a source language, but requires a regional
# variant when English is the target.
_SOURCE_LANG_CODES = {"en": "EN", "de": "DE", "fr": "FR"}
_TARGET_LANG_CODES = {"en": "EN-US", "de": "DE", "fr": "FR"}

# Connection-level failures (DNS resolution, connect timeout, ...) are
# usually a transient blip on our side or DeepL's, not a reason to give up -
# a couple of quick retries clears most of them. A 4xx/5xx response (bad
# auth key, unsupported language, ...) is not retried here since trying
# again won't change the outcome.
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 1.0


class TranslationError(Exception):
    pass


async def translate_text(text: str, *, source_lang: str, target_lang: str) -> str:
    if settings.environment == "test":
        return f"[{target_lang}] {text}"

    last_exc: Exception = TranslationError("DeepL translation failed: no attempt was made")
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    settings.deepl_api_url,
                    headers={"Authorization": f"DeepL-Auth-Key {settings.deepl_api_key}"},
                    data={
                        "text": text,
                        "source_lang": _SOURCE_LANG_CODES[source_lang],
                        "target_lang": _TARGET_LANG_CODES[target_lang],
                    },
                )
                response.raise_for_status()
                return response.json()["translations"][0]["text"]
        except httpx.TransportError as exc:
            last_exc = exc
            if attempt < _MAX_ATTEMPTS:
                logger.warning(
                    "DeepL request failed (attempt %d/%d), retrying: %s",
                    attempt,
                    _MAX_ATTEMPTS,
                    exc,
                )
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)
                continue
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            raise TranslationError(f"DeepL translation failed: {exc}") from exc

    raise TranslationError(f"DeepL translation failed: {last_exc}") from last_exc

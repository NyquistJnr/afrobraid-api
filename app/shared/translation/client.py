import httpx

from app.core.config import get_settings

settings = get_settings()

# DeepL accepts plain "EN" as a source language, but requires a regional
# variant when English is the target.
_SOURCE_LANG_CODES = {"en": "EN", "de": "DE", "fr": "FR"}
_TARGET_LANG_CODES = {"en": "EN-US", "de": "DE", "fr": "FR"}


class TranslationError(Exception):
    pass


async def translate_text(text: str, *, source_lang: str, target_lang: str) -> str:
    if settings.environment == "test":
        return f"[{target_lang}] {text}"

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
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        raise TranslationError(f"DeepL translation failed: {exc}") from exc

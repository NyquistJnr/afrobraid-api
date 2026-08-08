import base64

import httpx

from app.core.config import get_settings

settings = get_settings()

# Steers the edit away from common instruct-pix2pix failure modes (changing
# the face/pose/background instead of just the hair) - image-to-image models
# like this one have no concept of "only touch the hair" on their own, so a
# negative prompt is the cheapest lever we have to keep the subject stable.
_NEGATIVE_PROMPT = (
    "different face, different person, changed background, changed pose, "
    "blurry, distorted, low quality"
)


class HuggingFaceApiError(Exception):
    pass


async def generate_hairstyle_image(image_bytes: bytes, *, instruction: str) -> bytes:
    """Sends a photo + an edit instruction (e.g. "give her a curly afro,
    shoulder length") to the configured Hugging Face image-to-image model and
    returns the generated image's bytes.

    `X-Wait-For-Model` tells HF's serverless Inference API to block until a
    cold model finishes loading rather than returning 503 immediately -
    paired with the long client timeout, this avoids needing our own
    retry/backoff loop for the common "model was asleep" case.
    """
    payload = {
        "inputs": base64.b64encode(image_bytes).decode("ascii"),
        "parameters": {
            "prompt": instruction,
            "negative_prompt": _NEGATIVE_PROMPT,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=settings.hf_request_timeout_seconds) as client:
            response = await client.post(
                f"{settings.hf_api_url}/{settings.hf_model_id}",
                headers={
                    "Authorization": f"Bearer {settings.hf_api_key}",
                    "X-Wait-For-Model": "true",
                },
                json=payload,
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                raise HuggingFaceApiError(
                    f"Expected an image response, got {content_type!r}: {response.text[:500]}"
                )
            return response.content
    except httpx.HTTPError as exc:
        raise HuggingFaceApiError(f"Hugging Face image generation failed: {exc}") from exc

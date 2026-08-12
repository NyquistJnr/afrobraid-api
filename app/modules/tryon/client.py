import io
from typing import Any, cast

from huggingface_hub import AsyncInferenceClient
from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError

from app.core.config import get_settings

settings = get_settings()

# Steers the edit away from common image-editing-model failure modes (changing
# the face/pose/background instead of just the hair) - image-to-image models
# have no built-in concept of "only touch the hair" on their own, so a
# negative prompt is the cheapest lever we have to keep the subject stable.
_NEGATIVE_PROMPT = (
    "different face, different person, changed background, changed pose, "
    "blurry, distorted, low quality"
)
_RESULT_FORMAT = "JPEG"


class HuggingFaceApiError(Exception):
    pass


class HuggingFaceCreditExhaustedError(HuggingFaceApiError):
    pass


def _is_credit_exhausted_error(exc: HfHubHTTPError) -> bool:
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    message = str(exc).lower()
    return status_code == 402 or any(
        phrase in message
        for phrase in (
            "credit",
            "quota",
            "billing",
            "payment required",
            "insufficient balance",
        )
    )


def _client() -> AsyncInferenceClient:
    # provider="auto" (Hugging Face's Inference Providers routing) picks
    # whichever partner provider currently serves hf_model_id fastest - the
    # old single-endpoint "serverless Inference API" this used to hit
    # (api-inference.huggingface.co) was fully decommissioned in favor of
    # this provider-routed model, so hand-rolling the HTTP call ourselves
    # would mean re-implementing provider-specific request/response formats
    # that change outside our control. The official client keeps that in sync.
    return AsyncInferenceClient(
        # hf_provider is a free-form config string (validated by the HF API
        # itself, not worth mirroring its Literal type here).
        provider=cast(Any, settings.hf_provider),
        token=settings.hf_api_key,
        timeout=settings.hf_request_timeout_seconds,
    )


async def generate_hairstyle_image(image_bytes: bytes, *, instruction: str) -> bytes:
    """Sends a photo + an edit instruction (e.g. "give her a curly afro,
    shoulder length") to the configured Hugging Face image-to-image model and
    returns the generated image's bytes (JPEG-encoded)."""
    try:
        result_image = await _client().image_to_image(
            image_bytes,
            prompt=instruction,
            negative_prompt=_NEGATIVE_PROMPT,
            model=settings.hf_model_id,
        )
    except HfHubHTTPError as exc:
        if _is_credit_exhausted_error(exc):
            raise HuggingFaceCreditExhaustedError(
                "Hugging Face AI credit is exhausted"
            ) from exc
        raise HuggingFaceApiError(f"Hugging Face image generation failed: {exc}") from exc
    except (InferenceTimeoutError, ConnectionError, OSError) as exc:
        raise HuggingFaceApiError(f"Hugging Face image generation failed: {exc}") from exc

    buffer = io.BytesIO()
    result_image.convert("RGB").save(buffer, format=_RESULT_FORMAT)
    return buffer.getvalue()

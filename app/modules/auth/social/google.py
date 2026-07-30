import asyncio

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import get_settings
from app.core.exceptions import SocialAuthError
from app.modules.auth.social.base import SocialProfile

settings = get_settings()


async def verify_token(token: str) -> SocialProfile:
    try:
        idinfo = await asyncio.to_thread(
            google_id_token.verify_oauth2_token,
            token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        raise SocialAuthError() from exc

    email = idinfo.get("email")
    if not email:
        raise SocialAuthError()

    given_name = idinfo.get("given_name") or (idinfo.get("name") or "User").split(" ")[0]

    return SocialProfile(
        provider_user_id=idinfo["sub"],
        email=email,
        first_name=given_name or "User",
        last_name=idinfo.get("family_name"),
        email_verified=bool(idinfo.get("email_verified", True)),
    )

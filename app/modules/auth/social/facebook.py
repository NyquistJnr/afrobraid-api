import httpx

from app.core.config import get_settings
from app.core.exceptions import SocialAuthError
from app.modules.auth.social.base import SocialProfile

settings = get_settings()

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


async def verify_token(token: str) -> SocialProfile:
    app_access_token = f"{settings.facebook_app_id}|{settings.facebook_app_secret}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        debug_resp = await client.get(
            f"{GRAPH_API_BASE}/debug_token",
            params={"input_token": token, "access_token": app_access_token},
        )
        if debug_resp.status_code != 200:
            raise SocialAuthError()

        debug_data = debug_resp.json().get("data", {})
        if not debug_data.get("is_valid") or str(debug_data.get("app_id")) != str(
            settings.facebook_app_id
        ):
            raise SocialAuthError()

        profile_resp = await client.get(
            f"{GRAPH_API_BASE}/me",
            params={"fields": "id,email,first_name,last_name", "access_token": token},
        )
        if profile_resp.status_code != 200:
            raise SocialAuthError()
        profile = profile_resp.json()

    email = profile.get("email")
    if not email:
        raise SocialAuthError()

    return SocialProfile(
        provider_user_id=profile["id"],
        email=email,
        first_name=profile.get("first_name") or "User",
        last_name=profile.get("last_name"),
        email_verified=True,
    )

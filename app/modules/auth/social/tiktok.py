import httpx

from app.core.exceptions import SocialAuthError
from app.modules.auth.social.base import SocialProfile

TIKTOK_USERINFO_URL = "https://open.tiktokapis.com/v2/user/info/"


async def verify_token(token: str) -> SocialProfile:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            TIKTOK_USERINFO_URL,
            params={"fields": "open_id,display_name,email"},
            headers={"Authorization": f"Bearer {token}"},
        )

    if resp.status_code != 200:
        raise SocialAuthError()

    payload = resp.json()
    error = payload.get("error") or {}
    if error.get("code") not in (None, "ok"):
        raise SocialAuthError()

    user = payload.get("data", {}).get("user", {})
    email = user.get("email")
    if not email:
        # TikTok only returns email for apps explicitly approved for the
        # user.info.profile email scope; without it, TikTok signup cannot
        # satisfy our email-required schema.
        raise SocialAuthError()

    display_name = user.get("display_name") or "User"
    first_name, _, last_name = display_name.partition(" ")

    return SocialProfile(
        provider_user_id=user["open_id"],
        email=email,
        first_name=first_name or "User",
        last_name=last_name or None,
        email_verified=True,
    )

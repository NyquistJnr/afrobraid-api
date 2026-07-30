from collections.abc import Awaitable, Callable

from app.core.exceptions import UnsupportedProviderError
from app.modules.auth.social import facebook, google, tiktok
from app.modules.auth.social.base import SocialProfile
from app.modules.users.models import AuthProvider

_VERIFIERS: dict[AuthProvider, Callable[[str], Awaitable[SocialProfile]]] = {
    AuthProvider.GOOGLE: google.verify_token,
    AuthProvider.FACEBOOK: facebook.verify_token,
    AuthProvider.TIKTOK: tiktok.verify_token,
}


async def verify_social_token(provider: AuthProvider, token: str) -> SocialProfile:
    verifier = _VERIFIERS.get(provider)
    if verifier is None:
        raise UnsupportedProviderError()
    return await verifier(token)

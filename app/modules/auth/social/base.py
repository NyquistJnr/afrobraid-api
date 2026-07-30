from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SocialProfile:
    provider_user_id: str
    email: str
    first_name: str
    last_name: str | None
    email_verified: bool


class SocialVerifier(Protocol):
    async def __call__(self, token: str) -> SocialProfile: ...

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import UserType
from tests.helpers import create_user_with_token
from tests.modules.bookings.helpers import create_bookable_braider

pytestmark = pytest.mark.asyncio

ADMIN_USERS_URL = "/api/v1/admin/users"


async def test_admin_braider_user_list_includes_braider_id(
    client: AsyncClient, db_session: AsyncSession
):
    braider = await create_bookable_braider(db_session, business_name="Profiled Braider")
    bare_braider_user, _ = await create_user_with_token(db_session, user_type=UserType.BRAIDER)
    _, admin_token = await create_user_with_token(db_session, user_type=UserType.ADMIN)

    resp = await client.get(
        ADMIN_USERS_URL,
        params={"user_type": "BRAIDER", "page": 1, "page_size": 40},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text

    items = resp.json()["data"]["items"]
    by_user_id = {item["id"]: item for item in items}
    assert by_user_id[str(braider["user"].id)]["braider_id"] == str(braider["braider_id"])
    assert by_user_id[str(bare_braider_user.id)]["braider_id"] is None

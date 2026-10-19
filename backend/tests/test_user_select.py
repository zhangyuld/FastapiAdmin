"""业务用户下拉不依赖系统菜单，但不能越过登录和数据范围。"""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.base_schema import AuthSchema, CoreUserSchema
from app.core.database import async_db_session
from app.core.dependencies import get_current_user
from app.core.permission import Permission
from app.modules.system.user.model import UserModel

SELECT_PATH = "/system/user/list/all"


@pytest.fixture
def inventory_user(test_client: TestClient) -> Generator[AuthSchema, None, None]:
    """模拟仅持有进销存查询权限的普通用户，保留真实查询和范围逻辑。"""
    auth = AuthSchema(user=CoreUserSchema(id=3, username="user", is_superuser=False), permissions=["module_inventory:goods:query"])
    overrides = test_client.app.dependency_overrides
    previous = overrides.get(get_current_user)
    overrides[get_current_user] = lambda: auth
    try:
        yield auth
    finally:
        if previous is None:
            overrides.pop(get_current_user, None)
        else:
            overrides[get_current_user] = previous


@pytest.fixture
def select_users(test_client: TestClient) -> Generator[dict[str, int], None, None]:
    """在临时库准备启用、停用及软删除用户，按确切主键清理。"""
    async def prepare() -> dict[str, int]:
        async with async_db_session() as db, db.begin():
            users = {
                key: UserModel(username=f"select_test_{key}", name=f"Select {key}", password="not-a-login-hash", status=status, is_deleted=deleted, created_id=3)
                for key, status, deleted in [("active", 0, False), ("disabled", 1, False), ("deleted", 0, True)]
            }
            db.add_all(users.values())
            await db.flush()
            return {key: user.id for key, user in users.items()}

    async def cleanup(ids: list[int]) -> None:
        async with async_db_session() as db, db.begin():
            await db.execute(delete(UserModel).where(UserModel.id.in_(ids)))

    ids = test_client.portal.call(prepare)
    try:
        yield ids
    finally:
        test_client.portal.call(cleanup, list(ids.values()))


def test_user_select_requires_login(test_client: TestClient) -> None:
    """取消用户管理权限不等于允许匿名访问。"""
    assert test_client.get(SELECT_PATH).status_code == 401


def test_inventory_user_can_select_without_system_permission(test_client: TestClient, inventory_user: AuthSchema, select_users: dict[str, int]) -> None:
    """仅业务授权也能获取数据范围内的精简选项。"""
    with patch.object(Permission, "_load_user_data_scopes", new=AsyncMock(return_value={Permission.DATA_SCOPE_ALL})):
        response = test_client.get(SELECT_PATH)
    assert response.status_code == 200, response.text
    options = response.json()["data"]
    ids = {item["id"] for item in options}
    assert select_users["active"] in ids
    assert select_users["disabled"] not in ids
    assert select_users["deleted"] not in ids
    assert all(set(item) == {"id", "username", "name"} for item in options)


def test_user_select_preserves_self_scope(test_client: TestClient, inventory_user: AuthSchema, select_users: dict[str, int]) -> None:
    """仅本人范围不能因公共下拉接口而读取其他用户。"""
    with patch.object(Permission, "_load_user_data_scopes", new=AsyncMock(return_value={Permission.DATA_SCOPE_SELF})):
        response = test_client.get(SELECT_PATH)
    assert response.status_code == 200, response.text
    assert {item["id"] for item in response.json()["data"]} == {inventory_user.user.id}


@pytest.mark.parametrize("path", ["/system/user/list", "/system/user/detail/3"])
def test_user_management_remains_protected(test_client: TestClient, inventory_user: AuthSchema, path: str) -> None:
    """下拉授权不赋予用户管理分页或详情权限。"""
    assert test_client.get(path).status_code == 403


def test_superuser_select_still_works(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    """超管仍可使用原有下拉接口。"""
    response = test_client.get(SELECT_PATH, headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["data"]

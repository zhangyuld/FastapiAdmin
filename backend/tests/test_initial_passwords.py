"""账号初始口令、种子哈希及用户创建/导入的默认策略。"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.base_schema import AuthSchema
from app.modules.system.user.schema import UserCreateSchema
from app.modules.system.user.service import UserService
from app.utils.password_util import PwdUtil


@pytest.mark.parametrize("username,password", [("super", "super123456@#"), ("admin", "admin123456@#"), ("buyer", "zcy123456@#")])
def test_account_default_and_seed_hash(username: str, password: str) -> None:
    """统一默认口令与旧兼容初始化种子使用相同策略。"""
    assert PwdUtil.default_initial_password(username) == password
    rows = json.loads((Path(__file__).parents[1] / "sql" / "sys_user.json").read_text(encoding="utf-8"))
    seed_user = "user" if username == "buyer" else username
    row = next(item for item in rows if item["username"] == seed_user)
    assert PwdUtil.verify_password(password, row["password"])


@pytest.mark.parametrize("username", ["super", "admin", "reader"])
@pytest.mark.parametrize("explicit", [False, True])
def test_environment_password_override(monkeypatch: pytest.MonkeyPatch, username: str, explicit: bool) -> None:
    """环境变量只在确实设置时覆盖账号默认值。"""
    from app.scripts.deployment.common import password_from_env

    if explicit:
        monkeypatch.setenv("TEST_INITIAL_PASSWORD", "Override#2026")
    else:
        monkeypatch.delenv("TEST_INITIAL_PASSWORD", raising=False)
    expected = "Override#2026" if explicit else PwdUtil.default_initial_password(username)
    assert password_from_env("TEST_INITIAL_PASSWORD", username) == expected


@pytest.mark.parametrize("explicit", [None, "Explicit#2026"])
def test_create_password_default_and_override(explicit: str | None) -> None:
    """未填口令时采用默认值，显式口令不被覆盖。"""
    async def create() -> None:
        """隔离CRUD，只检查交给持久化层的口令哈希。"""
        service = UserService(AuthSchema(), AsyncMock())
        crud = SimpleNamespace(get=AsyncMock(return_value=None), create=AsyncMock(return_value=SimpleNamespace(id=100)))
        with patch("app.modules.system.user.service.UserCRUD", return_value=crud), patch.object(service, "_set_user_roles", new=AsyncMock()), patch.object(service, "_set_user_positions", new=AsyncMock()), patch.object(service, "detail", new=AsyncMock()):
            await service.create(UserCreateSchema(username="new_reader", name="查询员", password=explicit))
        values = crud.create.call_args.kwargs["data"]
        assert PwdUtil.verify_password(explicit or "zcy123456@#", values["password"])

    asyncio.run(create())


@pytest.mark.parametrize("existing", [True, False])
def test_import_preserves_existing_password(existing: bool) -> None:
    """批量导入仅新建时设置默认口令，更新资料不重置密码。"""
    async def import_row() -> None:
        """模拟部门与用户查找，不读写真实数据库。"""
        service = UserService(AuthSchema(), AsyncMock())
        user = SimpleNamespace(id=100, is_superuser=False) if existing else None
        crud = SimpleNamespace(get=AsyncMock(return_value=user), update=AsyncMock(), create=AsyncMock(return_value=SimpleNamespace(id=101)))
        department = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(id=1)))
        row = {"username": "import_reader", "name": "查询员", "dept_id": 1, "status": "正常"}
        with patch("app.modules.system.user.service.UserCRUD", return_value=crud), patch("app.modules.system.user.service.DeptCRUD", return_value=department), patch.object(service, "_set_user_roles", new=AsyncMock()), patch.object(service, "_set_user_positions", new=AsyncMock()), patch("app.modules.system.user.service.settings.PASSWORD_IMPORT_DEFAULT", "zcy123456@#"):
            count, error = await service._process_import_row(2, row, True)
        assert count == 1 and error is None
        if existing:
            data = crud.update.call_args.kwargs["data"].model_dump(exclude_unset=True)
            assert "password" not in data
        else:
            assert PwdUtil.verify_password("zcy123456@#", crud.create.call_args.kwargs["data"]["password"])

    asyncio.run(import_row())

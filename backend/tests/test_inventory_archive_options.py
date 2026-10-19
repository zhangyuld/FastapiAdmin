"""轻量档案选项：登录边界、字段投影、状态、软删除及分页。"""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.base_schema import AuthSchema, CoreUserSchema
from app.core.database import async_db_session, async_engine
from app.core.dependencies import get_current_user
from app.modules.inventory.basic.model import CustomerModel, GoodsCategoryModel, SupplierModel, WarehouseModel


@pytest.fixture(autouse=True)
def isolate_background_audit() -> Generator[None, None, None]:
    """临时SQLite不运行异步审计写入，保留真实鉴权与查询行为。"""
    with patch("app.core.router_class._write_operation_log_async", new=AsyncMock()):
        yield


@pytest.fixture
def ordinary_client(test_client: TestClient) -> Generator[TestClient, None, None]:
    """仅替换认证身份，不替换AuthPermission，证明没有档案权限仍可读取选项。"""
    auth = AuthSchema(user=CoreUserSchema(id=1, is_superuser=False), permissions=["module_inventory:purchase_in:query"])
    overrides = test_client.app.dependency_overrides
    previous = overrides.get(get_current_user)
    overrides[get_current_user] = lambda: auth
    try:
        yield test_client
    finally:
        if previous is None:
            overrides.pop(get_current_user, None)
        else:
            overrides[get_current_user] = previous


@pytest.mark.parametrize("kind", ["category", "customer", "supplier", "warehouse"])
def test_options_require_authentication(test_client: TestClient, kind: str) -> None:
    """无凭据及无效凭据都不可匿名读取基础档案。"""
    url = f"/inventory/basic/{kind}/options"
    assert test_client.get(url).status_code == 401
    assert test_client.get(url, headers={"Authorization": "Bearer invalid-token"}).status_code == 401


@pytest.mark.parametrize("kind", ["customer", "supplier", "warehouse"])
def test_archive_options_fields_status_pagination_and_permissions(ordinary_client: TestClient, kind: str) -> None:
    """真正从数据库分页，查询必要列，并保持管理接口的403边界。"""
    model = {"customer": CustomerModel, "supplier": SupplierModel, "warehouse": WarehouseModel}[kind]
    prefix = f"OPTION-{kind.upper()}-"

    async def prepare() -> None:
        """写入52条启用、1条停用、1条已删除，仅写入测试库。"""
        async with async_db_session() as db, db.begin():
            for index in range(54):
                values: dict[str, Any] = {
                    f"{kind}_code": prefix + str(index),
                    f"{kind}_name": f"选项名称{index}",
                    "status": int(index == 52),
                    "is_deleted": index == 53,
                    "remark": "私有备注",
                    "address": "私有地址",
                }
                if kind != "warehouse":
                    values.update(contact="私有联系人", phone="13800138000")
                else:
                    values["is_default"] = index == 51
                db.add(model(**values))

    ordinary_client.portal.call(prepare)
    statements: list[str] = []

    def record_sql(_connection, _cursor, statement, _parameters, _context, _executemany) -> None:
        """记录真实SQL，确认没有全量ORM字段和用户关系。"""
        if f"from ims_{kind}" in statement.lower():
            statements.append(statement.lower())

    event.listen(async_engine.sync_engine, "before_cursor_execute", record_sql)
    url = f"/inventory/basic/{kind}"
    try:
        first = ordinary_client.get(url + "/options", params={"keyword": prefix, "page_size": 50})
        assert first.status_code == 200, first.text
        first_data = first.json()["data"]
        assert first_data["total"] == 53 and first_data["has_next"] is True
        assert len(first_data["items"]) == 50
        second = ordinary_client.get(url + "/options", params={"keyword": prefix, "page_no": 2, "page_size": 50}).json()["data"]
        assert len(second["items"]) == 3 and second["has_next"] is False
        assert len({row["id"] for row in first_data["items"] + second["items"]}) == 53
        fields = {"id", f"{kind}_code", f"{kind}_name", "status"} | ({"is_default"} if kind == "warehouse" else set())
        assert all(set(row) == fields for row in first_data["items"] + second["items"])
        if kind == "warehouse":
            assert first_data["items"][0]["is_default"] is True
        for status, total in [(0, 52), (1, 1)]:
            result = ordinary_client.get(url + "/options", params={"keyword": prefix, "status": status}).json()["data"]
            assert result["total"] == total
            assert all(row["status"] == status for row in result["items"])
        assert ordinary_client.get(url + "/options", params={"keyword": "私有联系人"}).json()["data"]["total"] == 0
        assert statements
        assert all(not any(field in statement for field in (".contact", ".phone", ".address", ".remark", ".created_id", "join sys_user")) for statement in statements)
        assert ordinary_client.get(url + "/list").status_code == 403
        assert ordinary_client.get(url + f"/detail/{first_data['items'][0]['id']}").status_code == 403
        assert ordinary_client.post(url + "/export", json={}).status_code == 403
    finally:
        event.remove(async_engine.sync_engine, "before_cursor_execute", record_sql)


def test_category_option_tree_and_filtered_orphan(ordinary_client: TestClient) -> None:
    """分类保留层级与排序，停用筛选后没有父级也不丢失节点。"""

    async def prepare() -> list[int]:
        async with async_db_session() as db, db.begin():
            parent = GoodsCategoryModel(name="选项测试根", sort=0, status=0)
            db.add(parent)
            await db.flush()
            children = [
                GoodsCategoryModel(name="选项测试启用", parent_id=parent.id, sort=1, status=0),
                GoodsCategoryModel(name="选项测试停用", parent_id=parent.id, sort=2, status=1),
                GoodsCategoryModel(name="选项测试删除", parent_id=parent.id, sort=3, status=0, is_deleted=True),
            ]
            db.add_all(children)
            await db.flush()
            return [parent.id, *[row.id for row in children]]

    parent_id, enabled_id, disabled_id, deleted_id = ordinary_client.portal.call(prepare)
    result = ordinary_client.get("/inventory/basic/category/options")
    assert result.status_code == 200, result.text
    parent = next(row for row in result.json()["data"] if row["id"] == parent_id)
    assert set(parent) == {"id", "name", "parent_id", "status", "children"}
    assert [row["id"] for row in parent["children"]] == [enabled_id, disabled_id]
    assert deleted_id not in [row["id"] for row in parent["children"]]
    disabled = ordinary_client.get("/inventory/basic/category/options", params={"status": 1}).json()["data"]
    assert any(row["id"] == disabled_id and row["parent_id"] == parent_id for row in disabled)
    assert ordinary_client.get("/inventory/basic/category/tree").status_code == 403


@pytest.mark.parametrize("query", [{"page_no": 0}, {"page_size": 101}, {"status": 2}, {"keyword": "a" * 201}])
def test_option_query_validation(ordinary_client: TestClient, query: dict[str, Any]) -> None:
    """非法分页、状态及超长关键词不可绕过参数边界。"""
    assert ordinary_client.get("/inventory/basic/customer/options", params=query).status_code == 422


def test_option_keyword_escapes_sql_wildcards(ordinary_client: TestClient) -> None:
    """通配符仅作为普通搜索文本，不能扩成任意编码。"""
    result = ordinary_client.get("/inventory/basic/customer/options", params={"keyword": "OPTION%CUSTOMER"})
    assert result.status_code == 200, result.text
    assert result.json()["data"]["total"] == 0

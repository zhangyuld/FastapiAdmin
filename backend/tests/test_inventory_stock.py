from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from test_inventory_purchase_in import disable_purchase_test_audit_writes as _disable_audit
from test_inventory_purchase_in import purchase_body as _purchase_body

from app.core.exceptions import CustomException
from app.modules.inventory.stock.posting import StockPostingService

purchase_body = _purchase_body
disable_purchase_test_audit_writes = _disable_audit
OPENING = "/inventory/stock/opening"
CHECK = "/inventory/stock/check"


@pytest.fixture
def opening_body(purchase_body: dict[str, Any]) -> dict[str, Any]:
    """复用独立档案，不连接开发数据库。"""
    return {
        "warehouse_id": purchase_body["warehouse_id"],
        "business_date": purchase_body["business_date"],
        "remark": "",
        "items": [{"goods_id": row["goods_id"], "quantity": "10.000", "unit_cost": "2.0000"} for row in purchase_body["items"]],
    }


def create(client: TestClient, headers: dict[str, str], base: str, body: dict) -> dict:
    """创建草稿并断言响应。"""
    response = client.post(base + "/create", headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def confirm(client: TestClient, headers: dict[str, str], base: str, document: dict) -> dict:
    """确认当前版本的库存单据。"""
    response = client.post(f"{base}/confirm/{document['id']}", headers=headers, json={"version": document["version"]})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def balance(client: TestClient, headers: dict[str, str], warehouse: int, goods: int) -> dict:
    """定位测试档案的共享余额。"""
    response = client.get("/inventory/stock/balance/list", headers=headers, params={"warehouse_id": warehouse, "goods_id": goods})
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"][0]


def test_opening_lifecycle_and_reinitialize(test_client: TestClient, auth_headers: dict[str, str], opening_body: dict) -> None:
    """期初生效、重复初始化拦截、无后续业务作废及重新初始化。"""
    document = create(test_client, auth_headers, OPENING, opening_body)
    first = confirm(test_client, auth_headers, OPENING, document)
    assert first["status"] == 1
    goods = opening_body["items"][0]["goods_id"]
    row = balance(test_client, auth_headers, opening_body["warehouse_id"], goods)
    assert row["quantity"] == "10.000" and row["stock_amount"] == "20.00"
    duplicate = create(test_client, auth_headers, OPENING, opening_body)
    assert test_client.post(f"{OPENING}/confirm/{duplicate['id']}", headers=auth_headers, json={"version": 0}).status_code == 409
    response = test_client.post(f"{OPENING}/void/{first['id']}", headers=auth_headers, json={"version": 1, "void_reason": "录入错误"})
    assert response.status_code == 200, response.text
    assert balance(test_client, auth_headers, opening_body["warehouse_id"], goods)["quantity"] == "0.000"
    second = confirm(test_client, auth_headers, OPENING, duplicate)
    assert second["status"] == 1
    assert test_client.post(f"{OPENING}/confirm/{duplicate['id']}", headers=auth_headers, json={"version": 0}).status_code == 409


def test_check_mixed_gain_loss_and_void(test_client: TestClient, auth_headers: dict[str, str], opening_body: dict) -> None:
    """盘盈盘亏采用原库存成本，冲销恢复原余额。"""
    source = confirm(test_client, auth_headers, OPENING, create(test_client, auth_headers, OPENING, opening_body))
    body = {
        "warehouse_id": opening_body["warehouse_id"],
        "business_date": opening_body["business_date"],
        "items": [{"goods_id": row["goods_id"], "actual_quantity": str(quantity)} for row, quantity in zip(opening_body["items"], [12, 7], strict=True)],
    }
    draft = create(test_client, auth_headers, CHECK, body)
    assert all(row["balance_version"] == 1 for row in draft["items"])
    checked = confirm(test_client, auth_headers, CHECK, draft)
    assert {row["cost_amount"] for row in checked["items"]} == {"4.00", "-6.00"}
    assert test_client.post(f"{OPENING}/void/{source['id']}", headers=auth_headers, json={"version": 1, "void_reason": "禁止后续冲销"}).status_code == 409
    response = test_client.post(f"{CHECK}/void/{checked['id']}", headers=auth_headers, json={"version": 1, "void_reason": "盘点撤销"})
    assert response.status_code == 200, response.text
    for row in opening_body["items"]:
        assert balance(test_client, auth_headers, opening_body["warehouse_id"], row["goods_id"])["quantity"] == "10.000"


def test_snapshot_version_detects_quantity_restored(test_client: TestClient, auth_headers: dict[str, str], opening_body: dict) -> None:
    """数量和金额回到原值，库存版本变化仍阻止过期盘点确认。"""
    initial = create(test_client, auth_headers, OPENING, opening_body)
    draft = create(
        test_client,
        auth_headers,
        CHECK,
        {
            "warehouse_id": opening_body["warehouse_id"],
            "business_date": opening_body["business_date"],
            "items": [{"goods_id": opening_body["items"][0]["goods_id"], "actual_quantity": "1.000", "unit_cost": "2.0000"}],
        },
    )
    source = confirm(test_client, auth_headers, OPENING, initial)
    response = test_client.post(f"{OPENING}/void/{source['id']}", headers=auth_headers, json={"version": 1, "void_reason": "恢复零库存"})
    assert response.status_code == 200, response.text
    assert test_client.post(f"{CHECK}/confirm/{draft['id']}", headers=auth_headers, json={"version": 0}).status_code == 409
    response = test_client.post(f"{CHECK}/refresh/{draft['id']}", headers=auth_headers, json={"version": 0})
    assert response.status_code == 200, response.text
    refreshed = response.json()["data"]
    assert refreshed["version"] == 1
    assert refreshed["items"][0]["actual_quantity"] == "1.000"
    confirm(test_client, auth_headers, CHECK, refreshed)


def test_zero_stock_gain_requires_explicit_cost(test_client: TestClient, auth_headers: dict[str, str], opening_body: dict) -> None:
    """零库存盘盈无成本输入必须拒绝，明确零成本允许免费库存。"""
    body = {"warehouse_id": opening_body["warehouse_id"], "business_date": opening_body["business_date"], "items": [{"goods_id": opening_body["items"][0]["goods_id"], "actual_quantity": "2.000"}]}
    assert test_client.post(CHECK + "/create", headers=auth_headers, json=body).status_code == 400
    body["items"][0]["unit_cost"] = "0.0000"
    confirm(test_client, auth_headers, CHECK, create(test_client, auth_headers, CHECK, body))


@pytest.mark.parametrize("bad", ["0", "-1", "NaN", "1.0001", "9999999999999999"])
def test_opening_invalid_quantities(test_client: TestClient, auth_headers: dict[str, str], opening_body: dict, bad: str) -> None:
    """非法数量及超精度输入在 schema 层拒绝。"""
    opening_body["items"][0]["quantity"] = bad
    assert test_client.post(OPENING + "/create", headers=auth_headers, json=opening_body).status_code == 422


def test_read_routes_filters_and_exports(test_client: TestClient, auth_headers: dict[str, str], opening_body: dict) -> None:
    """只读模块提供详情与字段顺序导出，不暴露修改入口。"""
    source = confirm(test_client, auth_headers, OPENING, create(test_client, auth_headers, OPENING, opening_body))
    query = {"warehouse_id": opening_body["warehouse_id"], "goods_id": opening_body["items"][0]["goods_id"]}
    for kind in ("balance", "log"):
        base = "/inventory/stock/" + kind
        response = test_client.get(base + "/list", headers=auth_headers, params=query)
        assert response.status_code == 200, response.text
        row = response.json()["data"]["items"][0]
        assert test_client.get(f"{base}/detail/{row['id']}", headers=auth_headers).status_code == 200
        response = test_client.post(base + "/export", headers=auth_headers, json={"query": query, "fields": ["goods_name", "warehouse_name"], "format": "csv", "filename": "库存验证"})
        assert response.status_code == 200, response.text
        assert response.content.decode("utf-8-sig").splitlines()[0] == "商品名称,仓库"
        assert test_client.post(base + "/export", headers=auth_headers, json={"fields": ["not_allowed"]}).status_code == 422
        assert test_client.post(base + "/update/1", headers=auth_headers, json={}).status_code in (404, 405)
    assert test_client.get("/inventory/stock/log/list", headers=auth_headers, params={**query, "business_no": source["doc_no"]}).json()["data"]["total"] == 1
    assert test_client.get("/inventory/stock/balance/list", headers=auth_headers, params={**query, "quantity_state": "zero"}).json()["data"]["total"] == 0


def test_draft_updates_and_delete_versions(test_client: TestClient, auth_headers: dict[str, str], opening_body: dict) -> None:
    """草稿替换递增版本，批量删除对每张单据验证版本。"""
    draft = create(test_client, auth_headers, OPENING, opening_body)
    response = test_client.post(f"{OPENING}/update/{draft['id']}", headers=auth_headers, json={**opening_body, "version": 0})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["version"] == 1
    body = {"ids": [draft["id"]], "versions": {str(draft["id"]): 0}}
    assert test_client.post(OPENING + "/delete", headers=auth_headers, json=body).status_code == 409
    body["versions"][str(draft["id"])] = 1
    assert test_client.post(OPENING + "/delete", headers=auth_headers, json=body).status_code == 200
    assert test_client.get(f"{OPENING}/detail/{draft['id']}", headers=auth_headers).status_code == 404


def test_stock_post_failure_rolls_back(test_client: TestClient, auth_headers: dict[str, str], opening_body: dict) -> None:
    """库存写入失败不得提交主单状态或部分余额。"""
    draft = create(test_client, auth_headers, OPENING, opening_body)
    with patch.object(StockPostingService, "post", new=AsyncMock(side_effect=CustomException(msg="rollback", status_code=500))):
        response = test_client.post(f"{OPENING}/confirm/{draft['id']}", headers=auth_headers, json={"version": 0})
    assert response.status_code == 500
    assert test_client.get(f"{OPENING}/detail/{draft['id']}", headers=auth_headers).json()["data"]["status"] == 0


def test_check_full_loss_clears_tail_and_void_restores(test_client: TestClient, auth_headers: dict[str, str], opening_body: dict) -> None:
    """全部盘亏结清金额尾差，零差异确认不追加流水。"""
    opening_body["items"] = [dict(opening_body["items"][0], quantity="3.000", unit_cost="0.3333")]
    confirm(test_client, auth_headers, OPENING, create(test_client, auth_headers, OPENING, opening_body))
    goods = opening_body["items"][0]["goods_id"]
    body = {"warehouse_id": opening_body["warehouse_id"], "business_date": opening_body["business_date"], "items": [{"goods_id": goods, "actual_quantity": "3.000"}]}
    unchanged = confirm(test_client, auth_headers, CHECK, create(test_client, auth_headers, CHECK, body))
    assert test_client.get("/inventory/stock/log/list", headers=auth_headers, params={"business_no": unchanged["doc_no"]}).json()["data"]["total"] == 0
    body["items"][0]["actual_quantity"] = "0.000"
    checked = confirm(test_client, auth_headers, CHECK, create(test_client, auth_headers, CHECK, body))
    assert checked["items"][0]["cost_amount"] == "-1.00"
    row = balance(test_client, auth_headers, opening_body["warehouse_id"], goods)
    assert (row["quantity"], row["stock_amount"]) == ("0.000", "0.00")
    response = test_client.post(f"{CHECK}/void/{checked['id']}", headers=auth_headers, json={"version": 1, "void_reason": "复核"})
    assert response.status_code == 200, response.text
    assert balance(test_client, auth_headers, opening_body["warehouse_id"], goods)["stock_amount"] == "1.00"


def test_gain_void_insufficient_stock_rolls_back(test_client: TestClient, auth_headers: dict[str, str], opening_body: dict) -> None:
    """盘盈库存耗尽后禁止冲销，主单与库存保持已确认状态。"""
    goods = opening_body["items"][0]["goods_id"]
    body = {"warehouse_id": opening_body["warehouse_id"], "business_date": opening_body["business_date"], "items": [{"goods_id": goods, "actual_quantity": "2.000", "unit_cost": "2.0000"}]}
    gain = confirm(test_client, auth_headers, CHECK, create(test_client, auth_headers, CHECK, body))
    body["items"][0]["actual_quantity"] = "0.000"
    confirm(test_client, auth_headers, CHECK, create(test_client, auth_headers, CHECK, body))
    response = test_client.post(f"{CHECK}/void/{gain['id']}", headers=auth_headers, json={"version": 1, "void_reason": "已耗尽"})
    assert response.status_code == 409, response.text
    assert test_client.get(f"{CHECK}/detail/{gain['id']}", headers=auth_headers).json()["data"]["status"] == 1
    assert balance(test_client, auth_headers, opening_body["warehouse_id"], goods)["quantity"] == "0.000"


def test_edit_check_retains_original_snapshot(test_client: TestClient, auth_headers: dict[str, str], opening_body: dict) -> None:
    """同仓库编辑不能把过期盘点草稿静默转换成新快照。"""
    body = {
        "warehouse_id": opening_body["warehouse_id"],
        "business_date": opening_body["business_date"],
        "items": [{"goods_id": opening_body["items"][0]["goods_id"], "actual_quantity": "2.000", "unit_cost": "2.0000"}],
    }
    draft = create(test_client, auth_headers, CHECK, body)
    confirm(test_client, auth_headers, OPENING, create(test_client, auth_headers, OPENING, opening_body))
    response = test_client.post(f"{CHECK}/update/{draft['id']}", headers=auth_headers, json={**body, "version": 0})
    assert response.status_code == 200, response.text
    saved = response.json()["data"]
    assert saved["items"][0]["system_quantity"] == "0.000"
    assert test_client.post(f"{CHECK}/confirm/{draft['id']}", headers=auth_headers, json={"version": 1}).status_code == 409


def test_posted_stock_and_audit_failure_rollback(test_client: TestClient, auth_headers: dict[str, str], opening_body: dict) -> None:
    """库存流水已写入后业务日志失败，整个事务仍需回滚。"""
    from app.modules.inventory.common.business_log import BusinessLogService

    draft = create(test_client, auth_headers, OPENING, opening_body)
    with patch.object(BusinessLogService, "record", new=AsyncMock(side_effect=CustomException(msg="audit failed", status_code=500))):
        response = test_client.post(f"{OPENING}/confirm/{draft['id']}", headers=auth_headers, json={"version": 0})
    assert response.status_code == 500
    assert test_client.get(f"{OPENING}/detail/{draft['id']}", headers=auth_headers).json()["data"]["status"] == 0
    assert test_client.get("/inventory/stock/log/list", headers=auth_headers, params={"business_no": draft["doc_no"]}).json()["data"]["total"] == 0
    confirm(test_client, auth_headers, OPENING, draft)

def test_shared_stock_and_private_source_permissions(test_client: TestClient, auth_headers: dict[str, str], opening_body: dict) -> None:
    """有库存权限的普通用户能读共享余额，不能越权读取或确认他人期初单。"""
    from sqlalchemy import select

    from app.core.base_schema import AuthSchema, CoreUserSchema
    from app.core.database import async_db_session
    from app.core.dependencies import get_current_user
    from app.modules.system.user.model import UserModel

    document = confirm(test_client, auth_headers, OPENING, create(test_client, auth_headers, OPENING, opening_body))

    async def load_user() -> CoreUserSchema:
        """加载本人数据范围的真实种子用户。"""
        async with async_db_session() as db:
            user = (await db.execute(select(UserModel).where(UserModel.username == "user"))).scalar_one()
            return CoreUserSchema(id=user.id, username=user.username, name=user.name, dept_id=user.dept_id, is_superuser=False)

    auth = AuthSchema(user=test_client.portal.call(load_user), permissions=[
        "module_inventory:stock_balance:query", "module_inventory:stock_log:query",
        "module_inventory:stock_opening:detail", "module_inventory:stock_opening:confirm",
    ])
    previous = test_client.app.dependency_overrides.get(get_current_user)
    test_client.app.dependency_overrides[get_current_user] = lambda: auth
    try:
        query = {"warehouse_id": opening_body["warehouse_id"], "goods_id": opening_body["items"][0]["goods_id"]}
        for kind in ("balance", "log"):
            response = test_client.get(f"/inventory/stock/{kind}/list", params=query)
            assert response.status_code == 200 and response.json()["data"]["total"] == 1
        assert test_client.get(f"{OPENING}/detail/{document['id']}").status_code == 404
        assert test_client.post(f"{OPENING}/confirm/{document['id']}", json={"version": 1}).status_code == 404
        auth.permissions = []
        assert test_client.get("/inventory/stock/balance/list").status_code == 403
        assert test_client.get("/inventory/stock/log/list").status_code == 403
    finally:
        if previous is None:
            test_client.app.dependency_overrides.pop(get_current_user, None)
        else:
            test_client.app.dependency_overrides[get_current_user] = previous

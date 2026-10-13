import csv
import json
import re
from collections.abc import Generator
from copy import deepcopy
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO, StringIO
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import unquote
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import delete, func, select, update

from app.core.base_schema import AuthSchema, CoreUserSchema
from app.core.database import async_db_session
from app.core.dependencies import get_current_user
from app.core.exceptions import CustomException
from app.modules.inventory.basic.model import GoodsModel
from app.modules.inventory.common.business_log import BusinessLogService
from app.modules.inventory.common.model import BusinessLogModel
from app.modules.inventory.finance.model import FundAllocationModel, FundTransactionModel, ReceivableModel
from app.modules.inventory.finance.receivable import ReceivableService
from app.modules.inventory.sale.model import SaleOutItemModel, SaleOutModel, SaleReturnItemModel, SaleReturnModel
from app.modules.inventory.sale.out import crud as crud_module
from app.modules.inventory.sale.out import service as service_module
from app.modules.inventory.stock.model import StockBalanceModel, StockLogModel
from app.modules.inventory.stock.posting import StockPostingService
from app.modules.system.user.model import UserModel

BASE = "/inventory/sale/out"


@pytest.mark.parametrize("missing", ["log", "receivable"])
def test_sale_void_rejects_missing_original_posting(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any], missing: str) -> None:
    """历史入账不完整不能凭单据直接冲销或补造原流水。"""
    _seed_stock(test_client, sale_body)
    document = _confirm(test_client, auth_headers, _create(test_client, auth_headers, sale_body))

    async def remove_original() -> None:
        """模拟被错误删除的原入账数据。"""
        model = StockLogModel if missing == "log" else ReceivableModel
        async with async_db_session() as db, db.begin():
            await db.execute(delete(model).where(model.business_type == "sale_out", model.business_id == document["id"]))

    test_client.portal.call(remove_original)
    before = _accounting(test_client, sale_body)
    response = test_client.post(BASE + f"/void/{document['id']}", headers=auth_headers, json={"version": 1, "void_reason": "原记录缺失"})
    assert response.status_code == 409, response.text
    assert _accounting(test_client, sale_body) == before


def test_sale_state_transition_rejects_stale_orm(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any]) -> None:
    """即使业务层持有旧 ORM 版本，数据库状态更新仍原子阻止覆盖。"""
    _seed_stock(test_client, sale_body)
    document = _create(test_client, auth_headers, sale_body)

    async def submit_stale() -> None:
        """模拟读取后另一次更新先行完成，校验条件更新而非仅内存判断。"""
        async with async_db_session() as db, db.begin():
            user = await db.get(UserModel, document["created_id"])
            auth = AuthSchema(user=CoreUserSchema(id=user.id, username=user.username, name=user.name, is_superuser=True))
            crud = crud_module.SaleOutCRUD(auth, db)
            stale = await crud.get_document(document["id"])
            await db.execute(update(SaleOutModel).where(SaleOutModel.id == stale.id).values(version=1).execution_options(synchronize_session=False))
            with pytest.raises(CustomException):
                await crud.transition(stale, service_module.DocumentStatus.CONFIRMED, datetime.now(UTC))
            current = await crud.get_document(document["id"])
            assert current.version == 1 and current.status == 0

    test_client.portal.call(submit_stale)


def test_sale_stock_version_conflict_rolls_back(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """库存版本条件更新失败时，不留下新建余额或已确认状态。"""
    _seed_stock(test_client, sale_body)
    document = _create(test_client, auth_headers, sale_body)
    before = _accounting(test_client, sale_body)
    original = StockPostingService._lock_balance

    async def change_version(self: StockPostingService, warehouse_id: int, goods_id: int, *, create: bool) -> StockBalanceModel:
        """锁后注入版本变化，验证库存 CAS 防护及事务回滚。"""
        row = await original(self, warehouse_id, goods_id, create=create)
        await self.db.execute(update(StockBalanceModel).where(StockBalanceModel.id == row.id).values(version=row.version + 1).execution_options(synchronize_session=False))
        return row

    monkeypatch.setattr(StockPostingService, "_lock_balance", change_version)
    response = test_client.post(BASE + f"/confirm/{document['id']}", headers=auth_headers, json={"version": 0})
    assert response.status_code == 409, response.text
    assert _accounting(test_client, sale_body) == before
    current = test_client.get(BASE + f"/detail/{document['id']}", headers=auth_headers).json()["data"]
    assert current["status"] == 0 and current["version"] == 0


def test_purchase_to_sale_accounting(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any]) -> None:
    """真实采购确认供货后销售扣库，作废销售恢复原库存及应收净额。"""
    supplier = test_client.post(
        "/inventory/basic/supplier/create",
        headers=auth_headers,
        json={
            "supplier_code": "SUP" + uuid4().hex[:12],
            "supplier_name": "销售联动供货商",
            "status": 0,
            "contact": "联动测试",
            "phone": "13800138000",
        },
    )
    assert supplier.status_code == 200, supplier.text
    goods_id = sale_body["items"][0]["goods_id"]
    purchase = test_client.post(
        "/inventory/purchase/inbound/create",
        headers=auth_headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "warehouse_id": sale_body["warehouse_id"],
            "business_date": sale_body["business_date"],
            "items": [{"goods_id": goods_id, "quantity": "10", "unit_price": "2"}],
        },
    )
    assert purchase.status_code == 201, purchase.text
    response = test_client.post(f"/inventory/purchase/inbound/confirm/{purchase.json()['data']['id']}", headers=auth_headers, json={"version": 0})
    assert response.status_code == 200, response.text
    sale_body["items"] = [{"goods_id": goods_id, "quantity": "5", "unit_price": "6"}]
    sale_body["discount_amount"] = "2"
    document = _confirm(test_client, auth_headers, _create(test_client, auth_headers, sale_body))
    assert document["receivable_amount"] == "28.00"
    assert document["items"][0]["unit_cost"] == "2.0000" and document["items"][0]["cost_amount"] == "10.00"
    assert _accounting(test_client, sale_body)["balances"] == [(Decimal("5"), Decimal("10"), Decimal("2"), 2)]
    response = test_client.post(BASE + f"/void/{document['id']}", headers=auth_headers, json={"version": 1, "void_reason": "联动测试"})
    assert response.status_code == 200, response.text
    assert _accounting(test_client, sale_body)["balances"] == [(Decimal("10"), Decimal("20"), Decimal("2"), 3)]


def test_sale_partial_cost_uses_unrounded_average(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any]) -> None:
    """小单位成本不使用四位快照反算大批量金额，避免合法出库被舍入放大。"""
    sale_body["items"] = [{**sale_body["items"][0], "quantity": "9999", "unit_price": "0"}]
    _seed_stock(test_client, sale_body, "10000", "0.50")
    document = _confirm(test_client, auth_headers, _create(test_client, auth_headers, sale_body))
    assert document["items"][0]["unit_cost"] == "0.0001"
    assert document["items"][0]["cost_amount"] == "0.50"
    assert _accounting(test_client, sale_body)["balances"][0][:2] == (Decimal("1"), Decimal("0"))


def test_sale_confirmation_reversal_and_cost_tail(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any]) -> None:
    """销售售价与成本独立，连续出库结清尾差，作废按原成本恢复余额。"""
    sale_body["items"] = [{**sale_body["items"][0], "quantity": "1", "unit_price": "10"}]
    sale_body["discount_amount"] = "1.00"
    _seed_stock(test_client, sale_body)
    first = _create(test_client, auth_headers, sale_body)
    assert first["original_amount"] == "10.00" and first["receivable_amount"] == "9.00"
    assert first["items"][0]["unit_cost"] is None
    assert test_client.get(BASE + f"/returnable/{first['id']}", headers=auth_headers).status_code == 409
    first = _confirm(test_client, auth_headers, first)
    assert first["items"][0]["unit_cost"] == "0.3333" and first["items"][0]["cost_amount"] == "0.33"
    assert _accounting(test_client, sale_body)["balances"] == [(Decimal("2"), Decimal("0.67"), Decimal("0.3350"), 1)]
    before = _accounting(test_client, sale_body)
    assert test_client.post(BASE + f"/confirm/{first['id']}", headers=auth_headers, json={"version": 0}).status_code == 409
    assert test_client.post(BASE + f"/void/{first['id']}", headers=auth_headers, json={"version": 0, "void_reason": "旧版本"}).status_code == 409
    assert _accounting(test_client, sale_body) == before
    source = test_client.get(BASE + f"/returnable/{first['id']}", headers=auth_headers).json()["data"]
    assert source["items"][0]["returnable_amount"] == "9.00"
    sale_body["items"][0]["quantity"] = "2"
    second = _confirm(test_client, auth_headers, _create(test_client, auth_headers, sale_body))
    assert second["items"][0]["cost_amount"] == "0.67"
    assert _accounting(test_client, sale_body)["balances"] == [(Decimal("0"), Decimal("0"), Decimal("0"), 2)]
    for document in [first, second]:
        response = test_client.post(BASE + f"/void/{document['id']}", headers=auth_headers, json={"version": 1, "void_reason": "撤销销售"})
        assert response.status_code == 200, response.text
        assert response.json()["data"]["version"] == 2
        assert test_client.post(BASE + f"/void/{document['id']}", headers=auth_headers, json={"version": 2, "void_reason": "重复"}).status_code == 409
    after = _accounting(test_client, sale_body)
    assert after["balances"] == [(Decimal("3"), Decimal("1"), Decimal("0.3333"), 4)]
    assert sum(row[3] for row in after["logs"]) == 0 and sum(row[4] for row in after["logs"]) == 0
    assert sum(row[2] for row in after["bills"]) == 0
    assert len(after["bills"]) == 4
    original = {row[1]: row for row in after["logs"] if row[2] == "confirm"}
    for log in [row for row in after["logs"] if row[2] == "void"]:
        assert log[5] == original[log[1]][0] and log[3:5] == (-original[log[1]][3], -original[log[1]][4])


@pytest.mark.parametrize("kind", ["missing", "insufficient", "second_line"])
def test_sale_insufficient_stock_atomic(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any], kind: str) -> None:
    """任一商品无库存或库存不足时，整单状态、成本与记账均不改变。"""
    if kind != "missing":
        _seed_stock(test_client, sale_body, "0.5" if kind == "insufficient" else "3", "1")
    if kind == "second_line":
        sale_body["items"][1]["quantity"] = "4"
    document = _create(test_client, auth_headers, sale_body)
    before = _accounting(test_client, sale_body)
    response = test_client.post(BASE + f"/confirm/{document['id']}", headers=auth_headers, json={"version": 0})
    assert response.status_code == 409, response.text
    assert _accounting(test_client, sale_body) == before
    current = test_client.get(BASE + f"/detail/{document['id']}", headers=auth_headers).json()["data"]
    assert current["status"] == 0 and current["version"] == 0
    assert all(item["cost_amount"] is None for item in current["items"])


@pytest.mark.parametrize("discount", ["0.02", "0.03"])
def test_sale_discount_and_free_sale(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any], discount: str) -> None:
    """优惠超原价拒绝保存；全额优惠仍扣库存并生成已结清零应收。"""
    sale_body["discount_amount"] = discount
    if discount == "0.03":
        response = test_client.post(BASE + "/create", headers=auth_headers, json=sale_body)
        assert response.status_code == 400, response.text
        return
    _seed_stock(test_client, sale_body)
    document = _confirm(test_client, auth_headers, _create(test_client, auth_headers, sale_body))
    assert document["receivable_amount"] == "0.00"
    assert _accounting(test_client, sale_body)["bills"][0][2:7] == (Decimal("0"), Decimal("0"), Decimal("0"), None, 2)
    source = test_client.get(BASE + f"/returnable/{document['id']}", headers=auth_headers)
    assert source.status_code == 200, source.text
    assert all(item["returnable_amount"] == "0.00" for item in source.json()["data"]["items"])


def test_sale_refund_allocation_and_related_returns(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any]) -> None:
    """分摊优惠后扣减有效历史退款，关联列表保留草稿与作废历史。"""
    sale_body["items"] = [{**item, "quantity": "2", "unit_price": "1"} for item in sale_body["items"]]
    sale_body["discount_amount"] = "1.00"
    _seed_stock(test_client, sale_body)
    document = _confirm(test_client, auth_headers, _create(test_client, auth_headers, sale_body))
    return_id = _seed_return(test_client, document, 1, "1")
    draft_id = _seed_return(test_client, document, 0, "1")
    _seed_return(test_client, document, 2, "1")

    async def refund() -> None:
        """预置一半数量对应的已确认退款。"""
        async with async_db_session() as db, db.begin():
            await db.execute(update(SaleReturnModel).where(SaleReturnModel.id == return_id).values(return_amount=Decimal("0.75")))
            await db.execute(update(SaleReturnItemModel).where(SaleReturnItemModel.sale_return_id == return_id).values(line_amount=Decimal("0.75")))

    test_client.portal.call(refund)
    response = test_client.get(BASE + f"/returnable/{document['id']}", headers=auth_headers, params={"exclude_return_id": draft_id})
    assert response.status_code == 200, response.text
    source = response.json()["data"]
    assert [item["returnable_amount"] for item in source["items"]] == ["0.75", "1.50"]
    assert source["return_summary"] == {"return_status": "partial", "confirmed_count": 1, "returned_amount": "0.75"}
    response = test_client.get(BASE + f"/returns/{document['id']}", headers=auth_headers, params={"page_no": 1, "page_size": 2})
    assert response.status_code == 200, response.text
    page = response.json()["data"]
    assert page["total"] == 3 and page["has_next"] and len(page["items"]) == 2
    assert all("return_amount" in item and "original_amount" not in item for item in page["items"])


def _seed_stock(client: TestClient, body: dict[str, Any], quantity: str = "3", amount: str = "1") -> None:
    """为销售专项测试预置仓库余额，不伪造任何销售记账流水。"""

    async def seed() -> None:
        """在测试数据库中创建每个商品独立的余额。"""
        async with async_db_session() as db, db.begin():
            for item in body["items"]:
                db.add(
                    StockBalanceModel(
                        warehouse_id=body["warehouse_id"],
                        goods_id=item["goods_id"],
                        quantity=Decimal(quantity),
                        stock_amount=Decimal(amount),
                        avg_cost=(Decimal(amount) / Decimal(quantity)).quantize(Decimal("0.0001")),
                    )
                )

    client.portal.call(seed)


@pytest.fixture(scope="session", autouse=True)
def disable_sale_test_audit_writes() -> Generator[None, None, None]:
    """SQLite 测试中隔离另会话的审计写入，避免阻塞尚未提交的业务事务。"""
    with (
        patch("app.core.router_class._write_operation_log_async", new=AsyncMock()),
        patch("app.modules.system.auth.service._write_login_log", new=AsyncMock()),
    ):
        yield


@pytest.fixture
def sale_body(test_client: TestClient, auth_headers: dict[str, str]) -> dict[str, Any]:
    """创建互不冲突的启用档案，并生成两条销售明细入参。"""
    code = uuid4().hex[:12]
    category = test_client.post("/inventory/basic/category/create", headers=auth_headers, json={"name": "销售分类" + code, "parent_id": None, "sort": 1, "status": 0})
    assert category.status_code == 200, category.text
    customer = test_client.post(
        "/inventory/basic/customer/create",
        headers=auth_headers,
        json={
            "customer_name": "销售客户" + code,
            "customer_code": "SUP" + code,
            "contact": "测试联系人",
            "phone": "13800138000",
            "status": 0,
        },
    )
    assert customer.status_code == 200, customer.text
    warehouse = test_client.post("/inventory/basic/warehouse/create", headers=auth_headers, json={"warehouse_name": "销售仓库" + code, "warehouse_code": "WH" + code, "status": 0})
    assert warehouse.status_code == 200, warehouse.text
    goods_ids = []
    for index in range(2):
        response = test_client.post(
            "/inventory/basic/goods/create",
            headers=auth_headers,
            json={
                "goods_code": f"GOODS{code}{index}",
                "goods_name": f"销售商品{index}",
                "category_id": category.json()["data"]["id"],
                "spec": "规格A",
                "unit": "件",
                "reference_cost_price": "1",
                "sale_price": "2",
                "stock_min": "0",
                "stock_max": "0",
                "status": 0,
            },
        )
        assert response.status_code == 200, response.text
        goods_ids.append(response.json()["data"]["id"])
    return {
        "customer_id": customer.json()["data"]["id"],
        "warehouse_id": warehouse.json()["data"]["id"],
        "business_date": "2026-10-12",
        "remark": "  销售草稿  ",
        "items": [{"goods_id": id, "quantity": "1.000", "unit_price": "0.0050"} for id in goods_ids],
    }


def _create(client: TestClient, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    """创建草稿并要求接口正确返回明细，而非只返回主单。"""
    response = client.post(BASE + "/create", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_sale_draft_lifecycle(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any]) -> None:
    """草稿完成创建、筛选、更新、版本冲突及主从表软删除闭环。"""
    document = _create(test_client, auth_headers, sale_body)
    id = document["id"]
    assert document["original_amount"] == "0.02"
    assert document["status"] == 0 and document["version"] == 0
    assert document["remark"] == "销售草稿"
    assert document["customer_name"].startswith("销售客户")
    assert document["warehouse_name"].startswith("销售仓库")
    assert document["created_by"]["name"]
    assert [item["line_no"] for item in document["items"]] == [1, 2]
    assert [item["line_amount"] for item in document["items"]] == ["0.01", "0.01"]
    assert document["items"][0]["quantity"] == "1.000"
    assert document["items"][0]["unit_price"] == "0.0050"
    assert document["items"][0]["goods_code"].startswith("GOODS")

    listed = test_client.get(
        BASE + "/list",
        headers=auth_headers,
        params=[
            ("customer_id", sale_body["customer_id"]),
            ("warehouse_id", sale_body["warehouse_id"]),
            ("order_no", document["order_no"]),
            ("business_date", "2026-10-12"),
            ("business_date", "2026-10-12"),
            ("created_id", document["created_id"]),
            ("status", "0"),
            ("page_no", 1),
            ("page_size", 1),
        ],
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["total"] == 1
    assert "items" not in listed.json()["data"]["items"][0]
    excluded = test_client.get(BASE + "/list", headers=auth_headers, params=[("order_no", document["order_no"]), ("business_date", "2026-10-13"), ("business_date", "2026-10-14")])
    assert excluded.json()["data"]["total"] == 0

    body = deepcopy(sale_body)
    body.update(version=0, remark="")
    body["items"] = [{"goods_id": body["items"][1]["goods_id"], "quantity": "2.500", "unit_price": "1.2345"}]
    changed = test_client.post(BASE + f"/update/{id}", headers=auth_headers, json=body)
    assert changed.status_code == 200, changed.text
    current = changed.json()["data"]
    assert current["order_no"] == document["order_no"]
    assert current["version"] == 1 and current["remark"] is None
    assert current["original_amount"] == "3.09"
    assert len(current["items"]) == 1 and current["items"][0]["line_no"] == 1
    stale = test_client.post(BASE + f"/update/{id}", headers=auth_headers, json=body)
    assert stale.status_code == 409, stale.text
    assert test_client.post(BASE + "/delete", headers=auth_headers, json={"ids": [id], "versions": {id: 0}}).status_code == 409
    deleted = test_client.post(BASE + "/delete", headers=auth_headers, json={"ids": [id, id], "versions": {id: 1}})
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"] == [id]
    assert test_client.get(BASE + f"/detail/{id}", headers=auth_headers).status_code == 404

    async def inspect_deletion() -> tuple[bool, bool, int, int]:
        """直接检查主单与明细软删除，以及草稿未产生库存、应收。"""
        async with async_db_session() as db:
            main = await db.get(SaleOutModel, id)
            items = (await db.execute(select(SaleOutItemModel).where(SaleOutItemModel.sale_out_id == id))).scalars().all()
            stock = await db.scalar(select(func.count()).select_from(StockBalanceModel).where(StockBalanceModel.warehouse_id == sale_body["warehouse_id"]))
            receivable = await db.scalar(select(func.count()).select_from(ReceivableModel).where(ReceivableModel.customer_id == sale_body["customer_id"]))
            return main.is_deleted, all(item.is_deleted for item in items), stock, receivable

    assert test_client.portal.call(inspect_deletion) == (True, True, 0, 0)


@pytest.mark.parametrize("kind", ["customer", "warehouse", "goods"])
@pytest.mark.parametrize("deleted", [False, True])
def test_sale_rejects_inactive_archives(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any], kind: str, deleted: bool) -> None:
    """拒绝停用及已删除的客户、仓库和商品，失败不会产生主单。"""
    id = sale_body["items"][0]["goods_id"] if kind == "goods" else sale_body[kind + "_id"]
    path = f"/inventory/basic/{kind}/" + ("delete" if deleted else "status/batch")
    payload = {"ids": [id]} if deleted else {"ids": [id], "status": 1}
    if kind == "goods" and not deleted:

        async def disable_goods() -> None:
            """现有商品模块没有状态接口，测试直接预置停用状态。"""
            async with async_db_session() as db, db.begin():
                await db.execute(update(GoodsModel).where(GoodsModel.id == id).values(status=1))

        test_client.portal.call(disable_goods)
    else:
        response = test_client.post(path, headers=auth_headers, json=payload)
        assert response.status_code == 200, response.text
    result = test_client.post(BASE + "/create", headers=auth_headers, json=sale_body)
    assert result.status_code == (404 if deleted else 400), result.text
    listed = test_client.get(BASE + "/list", headers=auth_headers, params={"customer_id": sale_body["customer_id"]})
    assert listed.json()["data"]["total"] == 0


def test_sale_export_selected_columns(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any]) -> None:
    """全量导出保留筛选、字段顺序、显示状态和自定义或默认文件名。"""
    document = _create(test_client, auth_headers, sale_body)
    exported = test_client.post(
        BASE + "/export",
        headers=auth_headers,
        json={
            "query": {"order_no": document["order_no"]},
            "fields": ["original_amount", "order_no", "status", "created_name"],
            "format": "xlsx",
            "sheet_name": "销售测试",
            "filename": "销售记录.xlsx",
        },
    )
    assert exported.status_code == 200, exported.text
    assert "filename=sale_out.xlsx; filename*=" in exported.headers["content-disposition"]
    assert "销售记录.xlsx" in unquote(exported.headers["content-disposition"])
    workbook = load_workbook(BytesIO(exported.content), read_only=True)
    rows = list(workbook["销售测试"].iter_rows(values_only=True))
    workbook.close()
    assert rows[0] == ("原价合计", "单据编号", "状态", "创建人")
    assert len(rows) == 2
    assert rows[1][:3] == ("0.02", document["order_no"], "草稿")
    assert rows[1][3] == document["created_by"]["name"]

    csv_file = test_client.post(
        BASE + "/export",
        headers=auth_headers,
        json={
            "query": {"order_no": document["order_no"]},
            "fields": ["order_no", "customer_name"],
            "format": "csv",
            "filename": "",
        },
    )
    assert csv_file.status_code == 200, csv_file.text
    assert re.search(r"销售出库列表_\d{8}_\d{6}\.csv", unquote(csv_file.headers["content-disposition"]))
    csv_rows = list(csv.reader(StringIO(csv_file.content.decode("utf-8-sig"))))
    assert csv_rows == [["单据编号", "客户"], [document["order_no"], document["customer_name"]]]


def test_sale_rejects_amount_overflow_and_bad_sort(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any]) -> None:
    """明细精度虽合法，乘积或合计超数据库范围仍须拒绝。"""
    sale_body["items"] = [{"goods_id": sale_body["items"][0]["goods_id"], "quantity": "999999999999999.999", "unit_price": "99999999999999.9999"}]
    result = test_client.post(BASE + "/create", headers=auth_headers, json=sale_body)
    assert result.status_code == 400, result.text
    assert "销售金额超过允许范围" in result.json()["msg"]
    invalid = test_client.get(BASE + "/list", headers=auth_headers, params={"order_by": json.dumps([{"customer_name": "desc"}])})
    assert invalid.status_code == 422, invalid.text


def test_sale_original_amount_overflow(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any]) -> None:
    """各行金额未超限但合计超限时，仍应在写主从表前拒绝。"""
    for item in sale_body["items"]:
        item.update(quantity="999999999999999.999", unit_price="10.0000")
    response = test_client.post(BASE + "/create", headers=auth_headers, json=sale_body)
    assert response.status_code == 400, response.text
    listed = test_client.get(BASE + "/list", headers=auth_headers, params={"customer_id": sale_body["customer_id"]})
    assert listed.json()["data"]["total"] == 0


def test_sale_goods_snapshot_preserved(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any]) -> None:
    """商品档案改名后，已保存的明细仍展示原有快照。"""
    document = _create(test_client, auth_headers, sale_body)

    async def rename_goods() -> None:
        """直接变更档案名称，验证单据没有读取实时商品名称。"""
        async with async_db_session() as db, db.begin():
            await db.execute(update(GoodsModel).where(GoodsModel.id == sale_body["items"][0]["goods_id"]).values(goods_name="更名后的商品"))

    test_client.portal.call(rename_goods)
    current = test_client.get(BASE + f"/detail/{document['id']}", headers=auth_headers).json()["data"]
    assert current["items"][0]["goods_name"] == document["items"][0]["goods_name"]


def test_sale_crud_atomic_version_guard(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any]) -> None:
    """越过业务层的早期版本校验，SQL 本身仍拒绝旧版本修改和删除。"""
    document = _create(test_client, auth_headers, sale_body)
    changed = test_client.post(BASE + f"/update/{document['id']}", headers=auth_headers, json={**sale_body, "version": 0})
    assert changed.status_code == 200, changed.text

    async def submit_stale_version() -> tuple[bool, bool]:
        """使用独立事务模拟已持有旧版本的请求进行条件写入。"""
        async with async_db_session() as db, db.begin():
            auth = AuthSchema(user=CoreUserSchema(id=document["created_id"], is_superuser=True))
            crud = crud_module.SaleOutCRUD(auth, db)
            updated = await crud.update_draft(document["id"], 0, {"remark": "不应写入"}, [])
            deleted = await crud.delete_draft(document["id"], 0)
            return updated, deleted

    assert test_client.portal.call(submit_stale_version) == (False, False)
    current = test_client.get(BASE + f"/detail/{document['id']}", headers=auth_headers).json()["data"]
    assert current["version"] == 1 and current["remark"] == "销售草稿"
    assert len(current["items"]) == 2


@pytest.mark.parametrize("state", [1, 2])
def test_sale_non_draft_readonly(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any], state: int) -> None:
    """模拟后续生效或作废状态，现阶段接口不能修改或删除这些单据。"""
    document = _create(test_client, auth_headers, sale_body)

    async def set_status() -> None:
        """仅测试预置状态，不调用尚未实现的确认或作废功能。"""
        async with async_db_session() as db, db.begin():
            await db.execute(update(SaleOutModel).where(SaleOutModel.id == document["id"]).values(status=state))

    test_client.portal.call(set_status)
    updated = test_client.post(BASE + f"/update/{document['id']}", headers=auth_headers, json={**sale_body, "version": 0})
    deleted = test_client.post(BASE + "/delete", headers=auth_headers, json={"ids": [document["id"]], "versions": {document["id"]: 0}})
    assert updated.status_code == 409 and deleted.status_code == 409
    assert test_client.get(BASE + f"/detail/{document['id']}", headers=auth_headers).json()["data"]["status"] == state


@pytest.mark.parametrize("operation", ["create", "update"])
def test_sale_main_and_items_rollback(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any], monkeypatch: pytest.MonkeyPatch, operation: str) -> None:
    """明细写入后出错，创建和替换明细都必须连同主单整体回滚。"""
    document = _create(test_client, auth_headers, sale_body) if operation == "update" else None
    order_no = "ROLLBACK" + uuid4().hex
    monkeypatch.setattr(service_module.SaleOutService, "_generate_order_no", staticmethod(lambda: order_no))
    original = crud_module.SaleOutCRUD._add_items

    async def fail_after_items(self: Any, id: int, items: list[Any]) -> None:
        """模拟明细已经写入但事务提交前发生业务异常。"""
        await original(self, id, items)
        raise CustomException(msg="模拟明细写入失败", status_code=409)

    monkeypatch.setattr(crud_module.SaleOutCRUD, "_add_items", fail_after_items)
    body = deepcopy(sale_body)
    body["remark"] = "不应保存"
    if document:
        body.update(version=0)
        body["items"] = body["items"][:1]
        response = test_client.post(BASE + f"/update/{document['id']}", headers=auth_headers, json=body)
    else:
        response = test_client.post(BASE + "/create", headers=auth_headers, json=body)
    assert response.status_code == 409, response.text
    if document:
        current = test_client.get(BASE + f"/detail/{document['id']}", headers=auth_headers).json()["data"]
        assert current["version"] == 0 and current["remark"] == document["remark"]
        assert [item["id"] for item in current["items"]] == [item["id"] for item in document["items"]]
    else:
        listed = test_client.get(BASE + "/list", headers=auth_headers, params={"order_no": order_no})
        assert listed.json()["data"]["total"] == 0


def test_sale_batch_delete_rollback(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """批量删除第一张已写入后第二张发生版本冲突，整批仍须回滚。"""
    documents = [_create(test_client, auth_headers, sale_body) for _ in range(2)]
    original = crud_module.SaleOutCRUD.delete_draft
    calls = 0

    async def conflict_on_second(self: Any, id: int, version: int) -> bool:
        """模拟第二张草稿的原子版本校验失败。"""
        nonlocal calls
        calls += 1
        return False if calls == 2 else await original(self, id, version)

    monkeypatch.setattr(crud_module.SaleOutCRUD, "delete_draft", conflict_on_second)
    result = test_client.post(BASE + "/delete", headers=auth_headers, json={"ids": [item["id"] for item in documents], "versions": {item["id"]: 0 for item in documents}})
    assert result.status_code == 409, result.text
    for document in documents:
        current = test_client.get(BASE + f"/detail/{document['id']}", headers=auth_headers)
        assert current.status_code == 200, current.text
        assert current.json()["data"]["version"] == 0


def test_sale_data_scope_and_button_permission(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any]) -> None:
    """未登录不可访问；真实普通用户无权查询、修改、删除或导出他人的单据。"""
    document = _create(test_client, auth_headers, sale_body)
    assert test_client.get(BASE + "/list").status_code == 401

    async def load_user() -> CoreUserSchema:
        """加载数据范围为仅本人的种子用户。"""
        async with async_db_session() as db:
            user = (await db.execute(select(UserModel).where(UserModel.username == "user"))).scalar_one()
            return CoreUserSchema(id=user.id, username=user.username, name=user.name, dept_id=user.dept_id, is_superuser=False)

    auth = AuthSchema(
        user=test_client.portal.call(load_user), permissions=[f"module_inventory:sale_out:{action}" for action in ["query", "detail", "create", "update", "delete", "export", "confirm", "void"]]
    )
    previous = test_client.app.dependency_overrides.get(get_current_user)
    test_client.app.dependency_overrides[get_current_user] = lambda: auth
    try:
        listed = test_client.get(BASE + "/list", params={"order_no": document["order_no"]})
        assert listed.status_code == 200 and listed.json()["data"]["total"] == 0
        assert test_client.get(BASE + f"/detail/{document['id']}").status_code == 404
        assert test_client.get(BASE + f"/returnable/{document['id']}").status_code == 404
        assert test_client.post(BASE + f"/confirm/{document['id']}", json={"version": 0}).status_code == 404
        assert test_client.post(BASE + f"/void/{document['id']}", json={"version": 0, "void_reason": "测试"}).status_code == 404
        assert test_client.post(BASE + f"/update/{document['id']}", json={**sale_body, "version": 0}).status_code == 404
        assert test_client.post(BASE + "/delete", json={"ids": [document["id"]], "versions": {document["id"]: 0}}).status_code == 404
        exported = test_client.post(BASE + "/export", json={"query": {"order_no": document["order_no"]}, "fields": ["order_no"], "format": "csv"})
        assert list(csv.reader(StringIO(exported.content.decode("utf-8-sig")))) == [["单据编号"]]
        own = _create(test_client, {}, sale_body)
        assert own["created_id"] == auth.user.id
        assert test_client.get(BASE + f"/detail/{own['id']}").status_code == 200
        auth.permissions = []
        assert test_client.get(BASE + "/list").status_code == 403
        assert test_client.get(BASE + f"/returnable/{own['id']}").status_code == 403
        assert test_client.post(BASE + f"/confirm/{own['id']}", json={"version": 0}).status_code == 403
        assert test_client.post(BASE + f"/void/{own['id']}", json={"version": 0, "void_reason": "测试"}).status_code == 403
    finally:
        if previous is None:
            test_client.app.dependency_overrides.pop(get_current_user, None)
        else:
            test_client.app.dependency_overrides[get_current_user] = previous


def _confirm(client: TestClient, headers: dict[str, str], document: dict[str, Any]) -> dict[str, Any]:
    """确认单据并要求接口返回最新状态和明细。"""
    response = client.post(BASE + f"/confirm/{document['id']}", headers=headers, json={"version": document["version"]})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _accounting(client: TestClient, body: dict[str, Any]) -> dict[str, Any]:
    """读取当前测试仓库的完整记账快照，用于入账和回滚断言。"""

    async def inspect() -> dict[str, Any]:
        """同一测试事件循环读取库存、流水、应收和业务日志。"""
        async with async_db_session() as db:
            balances = (await db.execute(select(StockBalanceModel).where(StockBalanceModel.warehouse_id == body["warehouse_id"]).order_by(StockBalanceModel.goods_id))).scalars().all()
            logs = (await db.execute(select(StockLogModel).where(StockLogModel.warehouse_id == body["warehouse_id"]).order_by(StockLogModel.id))).scalars().all()
            bills = (await db.execute(select(ReceivableModel).where(ReceivableModel.customer_id == body["customer_id"]).order_by(ReceivableModel.id))).scalars().all()
            document_ids = select(SaleOutModel.id).where(SaleOutModel.warehouse_id == body["warehouse_id"])
            business_logs = (
                (await db.execute(select(BusinessLogModel).where(BusinessLogModel.business_type == "sale_out", BusinessLogModel.business_id.in_(document_ids)).order_by(BusinessLogModel.id)))
                .scalars()
                .all()
            )
            return {
                "balances": [(row.quantity, row.stock_amount, row.avg_cost, row.version) for row in balances],
                "logs": [(row.id, row.business_item_id, row.operation_type, row.change_quantity, row.cost_amount, row.reversal_log_id, row.is_deleted) for row in logs],
                "bills": [(row.id, row.operation_type, row.amount, row.allocated_amount, row.unallocated_amount, row.reversal_id, row.status, row.is_deleted) for row in bills],
                "audit": [(row.action, row.before_status, row.after_status, row.content) for row in business_logs],
            }

    return client.portal.call(inspect)


@pytest.mark.parametrize("operation", ["confirm", "void"])
@pytest.mark.parametrize("stage", ["stock", "receivable", "audit"])
def test_sale_posting_rollback(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any], monkeypatch: pytest.MonkeyPatch, operation: str, stage: str) -> None:
    """库存、应收或日志已写入后失败，余额、流水、状态和版本必须全部回滚。"""
    _seed_stock(test_client, sale_body)
    document = _create(test_client, auth_headers, sale_body)
    if operation == "void":
        document = _confirm(test_client, auth_headers, document)
    before = _accounting(test_client, sale_body)
    cls, method = {
        "stock": (StockPostingService, "post"),
        "receivable": (ReceivableService, "reverse" if operation == "void" else "create"),
        "audit": (BusinessLogService, "record"),
    }[stage]
    original = getattr(cls, method)

    async def fail_after_write(self: Any, *args: Any, **kwargs: Any) -> None:
        """注入写入后的业务失败以检查整个请求事务。"""
        await original(self, *args, **kwargs)
        raise CustomException(msg="模拟记账失败", status_code=409)

    monkeypatch.setattr(cls, method, fail_after_write)
    body = {"version": document["version"]}
    if operation == "void":
        body["void_reason"] = "测试冲销"
    response = test_client.post(BASE + f"/{operation}/{document['id']}", headers=auth_headers, json=body)
    assert response.status_code == 409, response.text
    current = test_client.get(BASE + f"/detail/{document['id']}", headers=auth_headers).json()["data"]
    assert current["status"] == document["status"] and current["version"] == document["version"]
    assert current["confirmed_time"] == document["confirmed_time"] and current["voided_time"] == document["voided_time"]
    assert _accounting(test_client, sale_body) == before


@pytest.mark.parametrize("allocation", [False, True])
def test_sale_void_rejects_settlement(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any], allocation: bool) -> None:
    """已核销金额或未撤销的核销记录任一存在，都必须阻止作废。"""
    _seed_stock(test_client, sale_body)
    document = _confirm(test_client, auth_headers, _create(test_client, auth_headers, sale_body))

    async def settle() -> None:
        """独立预置金额或核销记录，避免只检查其中一个字段。"""
        async with async_db_session() as db, db.begin():
            bill = (await db.execute(select(ReceivableModel).where(ReceivableModel.business_type == "sale_out", ReceivableModel.business_id == document["id"]))).scalar_one()
            if allocation:
                fund = FundTransactionModel(
                    transaction_no=uuid4().hex,
                    transaction_type="payment",
                    party_type="customer",
                    party_id=sale_body["customer_id"],
                    amount=Decimal("0.01"),
                    payment_method="cash",
                    business_date=date(2026, 10, 12),
                    status=1,
                )
                db.add(fund)
                await db.flush()
                db.add(FundAllocationModel(fund_transaction_id=fund.id, bill_type="receivable", bill_id=bill.id, allocated_amount=Decimal("0.01")))
            else:
                bill.allocated_amount = Decimal("0.01")
                bill.unallocated_amount = Decimal("0.01")
                bill.status = 1

    test_client.portal.call(settle)
    before = _accounting(test_client, sale_body)
    response = test_client.post(BASE + f"/void/{document['id']}", headers=auth_headers, json={"version": 1, "void_reason": "核销测试"})
    assert response.status_code == 409, response.text
    assert "核销" in response.json()["msg"] and _accounting(test_client, sale_body) == before


def _seed_return(client: TestClient, document: dict[str, Any], state: int, quantity: str, *, deleted: bool = False) -> int:
    """预置后续退货单及来源明细，不将尚未开发的退货接口纳入本阶段。"""

    async def create() -> int:
        """复制来源快照建立退货测试数据。"""
        async with async_db_session() as db, db.begin():
            main = SaleReturnModel(
                order_no="RETURN" + uuid4().hex,
                customer_id=document["customer_id"],
                warehouse_id=document["warehouse_id"],
                source_sale_out_id=document["id"],
                business_date=date(2026, 10, 12),
                return_amount=Decimal("0"),
                return_reason="测试退货",
                status=state,
                is_deleted=deleted,
                created_id=document["created_id"],
            )
            db.add(main)
            await db.flush()
            item = document["items"][0]
            db.add(
                SaleReturnItemModel(
                    sale_return_id=main.id,
                    source_sale_out_item_id=item["id"],
                    line_no=1,
                    goods_id=item["goods_id"],
                    goods_code=item["goods_code"],
                    goods_name=item["goods_name"],
                    spec=item["spec"],
                    unit=item["unit"],
                    quantity=Decimal(quantity),
                    unit_price=Decimal(item["unit_price"]),
                    unit_cost=Decimal(item["unit_price"]),
                    line_amount=Decimal("0"),
                    cost_amount=Decimal("0"),
                )
            )
            return main.id

    return client.portal.call(create)


def test_sale_returnable_rules_and_excluded_draft(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any]) -> None:
    """汇总多笔有效退货，忽略草稿、作废和删除记录，验证编辑排除参数归属。"""
    _seed_stock(test_client, sale_body)
    document = _confirm(test_client, auth_headers, _create(test_client, auth_headers, sale_body))
    draft_id = _seed_return(test_client, document, 0, "0.800")
    confirmed_id = _seed_return(test_client, document, 1, "0.200")
    _seed_return(test_client, document, 1, "0.100")
    _seed_return(test_client, document, 2, "0.900")
    _seed_return(test_client, document, 1, "0.900", deleted=True)
    result = test_client.get(BASE + f"/returnable/{document['id']}", headers=auth_headers, params={"exclude_return_id": draft_id})
    assert result.status_code == 200, result.text
    assert [item["returnable_quantity"] for item in result.json()["data"]["items"]] == ["0.700", "1.000"]
    assert test_client.get(BASE + f"/returnable/{document['id']}", headers=auth_headers, params={"exclude_return_id": confirmed_id}).status_code == 404
    other = _confirm(test_client, auth_headers, _create(test_client, auth_headers, sale_body))
    assert test_client.get(BASE + f"/returnable/{other['id']}", headers=auth_headers, params={"exclude_return_id": draft_id}).status_code == 404
    assert test_client.get(BASE + f"/returnable/{other['id']}", headers=auth_headers, params={"exclude_return_id": 999999}).status_code == 404
    assert test_client.get(BASE + f"/returnable/{other['id']}", headers=auth_headers, params={"exclude_return_id": 0}).status_code == 422


@pytest.mark.parametrize("state,deleted,expected", [(0, False, 409), (1, False, 409), (2, False, 200), (0, True, 200)])
def test_sale_void_linked_return_guard(test_client: TestClient, auth_headers: dict[str, str], sale_body: dict[str, Any], state: int, deleted: bool, expected: int) -> None:
    """任何未作废且未删除的来源退货阻止出库作废，避免留下无效来源草稿。"""
    _seed_stock(test_client, sale_body)
    document = _confirm(test_client, auth_headers, _create(test_client, auth_headers, sale_body))
    _seed_return(test_client, document, state, "0.100", deleted=deleted)
    result = test_client.post(BASE + f"/void/{document['id']}", headers=auth_headers, json={"version": 1, "void_reason": "关联退货检查"})
    assert result.status_code == expected, result.text

"""首页与正式报表口径对齐、权限裁剪、来源范围及分页回归。"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import test_inventory_finance as finance_fixtures
import test_inventory_purchase_report as purchase_fixtures
import test_inventory_sale_report as sale_fixtures
import test_inventory_stock_report as stock_fixtures
from sqlalchemy import select

from app.core.base_schema import AuthSchema, CoreUserSchema
from app.core.database import async_db_session
from app.core.dependencies import get_current_user
from app.modules.inventory.dashboard.service import DashboardService
from app.modules.inventory.sale.model import SaleOutModel
from app.modules.system.user.model import UserModel

PREFIX = "/inventory/dashboard"
NOW = datetime(2026, 10, 14, 8, tzinfo=timezone(timedelta(hours=8)))
ledger = finance_fixtures.ledger
purchase_data = purchase_fixtures.purchase_data
sale_data = sale_fixtures.sale_data
stock_report_data = stock_fixtures.stock_report_data


@pytest.fixture(autouse=True)
def dashboard_clock():
    """固定经营日期且关闭测试操作日志的后台异步写入。"""
    with patch.object(DashboardService, "now", return_value=NOW), patch("app.core.router_class._write_operation_log_async", new=AsyncMock()):
        yield


def data(client, headers, path, params=None):
    """断言统一成功响应并提取正式接口数据。"""
    response = client.get(path, headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest.mark.parametrize("kind,fixture", [("sale", "sale_data"), ("purchase", "purchase_data")])
def test_trade_summary_and_daily_match_reports(request, test_client, auth_headers, kind, fixture):
    """今日和本月由同一有效明细计算，跨月退货独立统计。"""
    request.getfixturevalue(fixture)
    summary = data(test_client, auth_headers, PREFIX + "/summary")
    for period, dates in [("today", ["2026-10-14", "2026-10-14"]), ("month", ["2026-10-01", "2026-10-14"])]:
        report = data(test_client, auth_headers, f"/inventory/report/{kind}/summary", {"business_date": dates})
        assert summary[kind + "_" + period] == {"net_amount": report[f"net_{kind}_amount"], "return_amount": report["return_amount"]}
    trend = data(test_client, auth_headers, PREFIX + "/trend", {"period": "month"})
    assert (trend["start_date"], trend["end_date"], len(trend["points"])) == ("2026-10-01", "2026-10-14", 14)
    assert sum(Decimal(row[kind + "_amount"]) for row in trend["points"]) == Decimal(summary[kind + "_month"]["net_amount"])
    for point in trend["points"]:
        report = data(test_client, auth_headers, f"/inventory/report/{kind}/summary", {"business_date": [point["business_date"]] * 2})
        assert point[kind + "_amount"] == report[f"net_{kind}_amount"]


def test_stock_amount_distribution_and_warning_paging(test_client, auth_headers, stock_report_data):
    """金额按实际余额、仓库分组与总额一致，预警边界与库存报表相同。"""
    summary = data(test_client, auth_headers, PREFIX + "/summary")
    stock = data(test_client, auth_headers, "/inventory/report/stock/summary")
    assert summary["stock_amount"] == stock["stock_amount"]
    warehouses = data(test_client, auth_headers, PREFIX + "/warehouse-stock")
    assert sum(Decimal(row["stock_amount"]) for row in warehouses) == Decimal(summary["stock_amount"])
    low = data(test_client, auth_headers, "/inventory/report/stock/list", {"warning": "low"})
    high = data(test_client, auth_headers, "/inventory/report/stock/list", {"warning": "high"})
    assert summary["warning_count"] == low["total"] + high["total"]
    page = data(test_client, auth_headers, PREFIX + "/stock-warnings", {"page_size": 1})
    assert page["total"] == summary["warning_count"]
    ids = [data(test_client, auth_headers, PREFIX + "/stock-warnings", {"page_size": 1, "page_no": n})["items"][0]["id"] for n in range(1, page["total"] + 1)]
    assert len(ids) == len(set(ids))
    assert page["has_next"] == (page["total"] > 1)


def test_finance_uses_positive_object_balances(test_client, auth_headers, ledger):
    """客户/供应商正向余额和冲减余额分别汇总，不跨对象抵消。"""
    summary = data(test_client, auth_headers, PREFIX + "/summary")
    finance = data(test_client, auth_headers, "/inventory/finance/" + ledger["kind"] + "/summary")
    assert summary[ledger["kind"]] == {field: finance[field] for field in ("positive_balance", "negative_balance")}


def test_no_permission_never_means_zero(test_client):
    """登录无经营授权仍可进入首页，指标 null，独立面板后端 403。"""
    auth = AuthSchema(user=CoreUserSchema(id=1, is_superuser=False), permissions=[])
    previous = test_client.app.dependency_overrides.get(get_current_user)
    test_client.app.dependency_overrides[get_current_user] = lambda: auth
    try:
        summary = data(test_client, {}, PREFIX + "/summary")
        assert all(value is None for key, value in summary.items() if key not in {"today", "as_of"})
        for endpoint in ("trend", "warehouse-stock", "stock-warnings", "recent-documents"):
            assert test_client.get(PREFIX + "/" + endpoint).status_code == 403
    finally:
        if previous is None:
            test_client.app.dependency_overrides.pop(get_current_user, None)
        else:
            test_client.app.dependency_overrides[get_current_user] = previous


def test_report_permissions_do_not_grant_source_data(test_client, auth_headers, sale_data):
    """销售报表单独授权不放出采购、库存、往来或来源单据。"""
    auth = AuthSchema(user=CoreUserSchema(id=1, is_superuser=False), permissions=["module_inventory:sale_report:query"])
    previous = test_client.app.dependency_overrides.get(get_current_user)
    test_client.app.dependency_overrides[get_current_user] = lambda: auth
    try:
        summary = data(test_client, {}, PREFIX + "/summary")
        assert summary["sale_month"] is not None
        assert summary["purchase_month"] is None and summary["stock_amount"] is None and summary["receivable"] is None
        points = data(test_client, {}, PREFIX + "/trend", {"period": "7d"})["points"]
        assert len(points) == 7 and all(row["purchase_amount"] is None and row["sale_amount"] is not None for row in points)
        assert test_client.get(PREFIX + "/recent-documents").status_code == 403
    finally:
        if previous is None:
            test_client.app.dependency_overrides.pop(get_current_user, None)
        else:
            test_client.app.dependency_overrides[get_current_user] = previous


def test_recent_respects_original_data_scope(test_client, auth_headers, sale_data):
    """来源查询先限制本人数据，再合并和限量，不泄漏他人创建单据。"""
    async def prepare():
        async with async_db_session() as db, db.begin():
            user = await db.scalar(select(UserModel).where(UserModel.username == "user"))
            row = await db.get(SaleOutModel, sale_data["original_id"])
            row.created_id = user.id
            return CoreUserSchema(id=user.id, username=user.username, dept_id=user.dept_id, is_superuser=False)

    auth = AuthSchema(user=test_client.portal.call(prepare), permissions=["module_inventory:sale_out:query"])
    previous = test_client.app.dependency_overrides.get(get_current_user)
    test_client.app.dependency_overrides[get_current_user] = lambda: auth
    try:
        rows = data(test_client, {}, PREFIX + "/recent-documents", {"limit": 20})
        assert {row["business_type"] for row in rows} <= {"sale_out"}
        assert any(row["business_id"] == sale_data["original_id"] for row in rows)
        assert not any(row["business_type"] == "sale_return" and row["business_id"] == sale_data["return_id"] for row in rows)
        assert len(rows) <= 20
    finally:
        if previous is None:
            test_client.app.dependency_overrides.pop(get_current_user, None)
        else:
            test_client.app.dependency_overrides[get_current_user] = previous


def test_empty_trade_period_is_real_zero(test_client, auth_headers):
    """有授权但无有效业务时指标为零，趋势保留全部日期的零值点。"""
    with patch("app.modules.inventory.dashboard.crud.DashboardCRUD.daily", new=AsyncMock(return_value=[])):
        summary = data(test_client, auth_headers, PREFIX + "/summary")
        assert summary["sale_today"] == summary["sale_month"] == {"net_amount": "0.00", "return_amount": "0.00"}
        points = data(test_client, auth_headers, PREFIX + "/trend", {"period": "30d"})["points"]
        assert len(points) == 30
        assert all(row["sale_amount"] == row["purchase_amount"] == "0.00" for row in points)


def test_void_return_recalculates_home(test_client, auth_headers, sale_data):
    """作废后移除原退货贡献，不把反向账单再次扣到经营指标。"""
    from app.modules.inventory.sale.model import SaleReturnModel

    before = data(test_client, auth_headers, PREFIX + "/summary")["sale_month"]

    async def void_return():
        async with async_db_session() as db, db.begin():
            returned = await db.get(SaleReturnModel, sale_data["return_id"])
            returned.status = 2

    test_client.portal.call(void_return)
    after = data(test_client, auth_headers, PREFIX + "/summary")["sale_month"]
    assert Decimal(after["net_amount"]) - Decimal(before["net_amount"]) == Decimal("30")
    assert Decimal(before["return_amount"]) - Decimal(after["return_amount"]) == Decimal("30")


@pytest.mark.parametrize("path,params", [("trend", {"period": "year"}), ("stock-warnings", {"page_no": 0}), ("stock-warnings", {"page_size": 51}), ("recent-documents", {"limit": 21})])
def test_invalid_queries(test_client, auth_headers, path, params):
    """限制期间和读取数量，异常请求不降级为无界查询。"""
    assert test_client.get(PREFIX + "/" + path, headers=auth_headers, params=params).status_code == 422

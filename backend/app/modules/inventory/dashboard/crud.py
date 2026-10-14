"""首页只读聚合复用报表筛选，最近单据独立遵循业务数据范围。"""

from datetime import date
from typing import Any

from sqlalchemy import String, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Subquery

from app.core.base_schema import AuthSchema
from app.core.permission import Permission
from app.modules.inventory.basic.model import GoodsModel
from app.modules.inventory.purchase.model import PurchaseInModel, PurchaseReturnModel
from app.modules.inventory.report.purchase.crud import PurchaseReportCRUD
from app.modules.inventory.report.purchase.schema import PurchaseReportQuery
from app.modules.inventory.report.sale.crud import SaleReportCRUD
from app.modules.inventory.report.sale.schema import SaleReportQuery
from app.modules.inventory.report.stock.crud import StockReportCRUD
from app.modules.inventory.report.stock.schema import StockReportQuery
from app.modules.inventory.sale.model import SaleOutModel, SaleReturnModel

from .schema import BusinessKind, WarningQuery


class DashboardCRUD:
    """不继承通用写入 CRUD，避免首页接口改变业务状态。"""

    def __init__(self, db: AsyncSession) -> None:
        """绑定请求内的数据库会话，查询依次执行。"""
        self.db = db

    async def daily(self, kind: str, start: date, end: date) -> list[dict[str, Any]]:
        """复用完整明细的确认、退货日期和销售优惠分摊，再按日汇总。"""
        if kind == "sale":
            lines = SaleReportCRUD(self.db)._lines(SaleReportQuery(business_date=[start, end]))
            incoming = lines.c.sale_amount
        else:
            lines = PurchaseReportCRUD(self.db)._lines(PurchaseReportQuery(business_date=[start, end]))
            incoming = lines.c.purchase_amount
        statement = select(
            lines.c.business_date,
            (func.sum(incoming) - func.sum(lines.c.return_amount)).label("net_amount"),
            func.sum(lines.c.return_amount).label("return_amount"),
        ).group_by(lines.c.business_date)
        return [dict(row) for row in (await self.db.execute(statement)).mappings()]

    @staticmethod
    def _stock() -> Subquery:
        """库存报表已建账筛选为首页金额与预警的共同基线。"""
        return StockReportCRUD._scope(StockReportQuery()).subquery("dashboard_stock")

    async def stock_summary(self) -> dict[str, Any]:
        """金额取实际余额，预警按商品仓库组合计数。"""
        rows = self._stock()
        statement = select(
            func.coalesce(func.sum(rows.c.stock_amount), 0).label("stock_amount"),
            select(func.count()).select_from(rows).where(rows.c.warning != "normal").scalar_subquery().label("warning_count"),
        ).select_from(rows)
        return dict((await self.db.execute(statement)).mappings().one())

    async def warehouses(self) -> list[dict[str, Any]]:
        """仓库金额与总库存使用同一余额范围，保留零金额仓库。"""
        rows = self._stock()
        statement = select(rows.c.warehouse_id, rows.c.warehouse_name, func.sum(rows.c.stock_amount).label("stock_amount")).group_by(rows.c.warehouse_id, rows.c.warehouse_name)
        statement = statement.order_by(func.sum(rows.c.stock_amount).desc(), rows.c.warehouse_id.asc())
        return [dict(row) for row in (await self.db.execute(statement)).mappings()]

    async def warnings(self, query: WarningQuery) -> tuple[list[dict[str, Any]], int]:
        """严格上下限筛选后稳定分页，补充商品阈值供页面展示。"""
        rows = self._stock()
        condition = rows.c.warning != "normal"
        total = await self.db.scalar(select(func.count()).select_from(rows).where(condition)) or 0
        statement = (
            select(rows, GoodsModel.stock_min, GoodsModel.stock_max)
            .join(GoodsModel, GoodsModel.id == rows.c.goods_id)
            .where(condition)
            .order_by(rows.c.warning.asc(), rows.c.warehouse_id.asc(), rows.c.goods_id.asc())
            .offset((query.page_no - 1) * query.page_size)
            .limit(query.page_size)
        )
        result = []
        for row in (await self.db.execute(statement)).mappings():
            result.append({**row, "id": f"{row['warehouse_id']}:{row['goods_id']}"})
        return result, total

    async def recent(self, auth: AuthSchema, kinds: list[BusinessKind], limit: int) -> list[dict[str, Any]]:
        """各来源先应用原业务创建人/部门数据权限，再合并选取最近单据。"""
        models = {
            "purchase_in": (PurchaseInModel, PurchaseInModel.total_amount),
            "purchase_return": (PurchaseReturnModel, PurchaseReturnModel.total_amount),
            "sale_out": (SaleOutModel, SaleOutModel.receivable_amount),
            "sale_return": (SaleReturnModel, SaleReturnModel.return_amount),
        }
        branches = []
        for kind in kinds:
            model, amount = models[kind]
            statement = select(
                literal(kind, type_=String(32)).label("business_type"),
                model.id.label("business_id"),
                model.order_no.label("business_no"),
                model.business_date,
                model.created_time,
                amount.label("amount"),
                model.status,
            ).where(model.is_deleted.is_(False))
            branches.append(await Permission(model, auth, self.db).filter_query(statement))
        if not branches:
            return []
        rows = union_all(*branches).subquery("dashboard_recent")
        statement = select(rows).order_by(rows.c.created_time.desc(), rows.c.business_type.asc(), rows.c.business_id.desc()).limit(limit)
        return [{**row, "id": f"{row['business_type']}:{row['business_id']}"} for row in (await self.db.execute(statement)).mappings()]

"""经营首页按领域授权返回数据，不把无权限误报为零业务。"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.inventory.finance.query_crud import FinanceQueryCRUD
from app.modules.inventory.finance.query_schema import BalanceQuery

from .crud import DashboardCRUD
from .schema import DashboardSummary, FinanceMetric, RecentDocument, StockWarningOut, TradeMetric, TrendOut, TrendPoint, WarehouseStock, WarningQuery


class DashboardService:
    """领域汇总共享企业数据，单据列表另执行来源数据权限。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """绑定认证和会话，不接受前端传入权限或统计基准日期。"""
        self.auth, self.db = auth, db
        self.crud = DashboardCRUD(db)

    def allowed(self, permission: str) -> bool:
        """沿用后端精确权限规则，超级管理员可查看所有领域。"""
        return bool(self.auth.user and (self.auth.user.is_superuser or permission in self.auth.permissions))

    def require(self, permission: str) -> None:
        """独立数据面板在后端拒绝未授权访问。"""
        if not self.allowed(permission):
            raise CustomException(msg="无权限查看该首页模块", status_code=403)

    @staticmethod
    def now() -> datetime:
        """今日和本月按北京时间定义，不受部署机器时区影响。"""
        return datetime.now(timezone(timedelta(hours=8)))

    async def summary(self) -> DashboardSummary:
        """汇总本月逐日金额并提取今日，库存及往来读取当前余额。"""
        now = self.now()
        today = now.date()
        result = DashboardSummary(as_of=now, today=today)
        for kind in ("sale", "purchase"):
            if not self.allowed(f"module_inventory:{kind}_report:query"):
                continue
            rows = await self.crud.daily(kind, today.replace(day=1), today)
            month = TradeMetric(net_amount=sum((row["net_amount"] for row in rows), Decimal("0")), return_amount=sum((row["return_amount"] for row in rows), Decimal("0")))
            day = next((row for row in rows if row["business_date"] == today), {"net_amount": Decimal("0"), "return_amount": Decimal("0")})
            setattr(result, kind + "_month", month)
            setattr(result, kind + "_today", TradeMetric.model_validate(day))
        if self.allowed("module_inventory:stock_report:query"):
            stock = await self.crud.stock_summary()
            result.stock_amount, result.warning_count = stock["stock_amount"], stock["warning_count"]
        for kind in ("receivable", "payable"):
            if self.allowed(f"module_inventory:{kind}:query"):
                values = await FinanceQueryCRUD(self.db, kind).summary(BalanceQuery())
                setattr(result, kind, FinanceMetric.model_validate(values))
        return result

    async def trend(self, period: str) -> TrendOut:
        """期间只影响经营趋势，有权限且无业务日期补零。"""
        today = self.now().date()
        start = today.replace(day=1) if period == "month" else today - timedelta(days=6 if period == "7d" else 29)
        by_kind = {}
        for kind in ("sale", "purchase"):
            if self.allowed(f"module_inventory:{kind}_report:query"):
                by_kind[kind] = {row["business_date"]: row["net_amount"] for row in await self.crud.daily(kind, start, today)}
        if not by_kind:
            raise CustomException(msg="无权限查看经营趋势", status_code=403)
        points = []
        for offset in range((today - start).days + 1):
            day = start + timedelta(days=offset)
            amounts = {kind + "_amount": values.get(day, Decimal("0")) for kind, values in by_kind.items()}
            points.append(TrendPoint(business_date=day, **amounts))
        return TrendOut(start_date=start, end_date=today, points=points)

    async def warehouses(self) -> list[WarehouseStock]:
        """仅库存报表授权可读取企业仓库金额分布。"""
        self.require("module_inventory:stock_report:query")
        return [WarehouseStock.model_validate(row) for row in await self.crud.warehouses()]

    async def warnings(self, query: WarningQuery) -> PageResultSchema[StockWarningOut]:
        """预警不借用普通业务查询权限扩大库存可见范围。"""
        self.require("module_inventory:stock_report:query")
        rows, total = await self.crud.warnings(query)
        return PageResultSchema(items=[StockWarningOut.model_validate(row) for row in rows], total=total, page_no=query.page_no, page_size=query.page_size, has_next=query.page_no * query.page_size < total)

    async def recent(self, limit: int) -> list[RecentDocument]:
        """只合并有来源查询权限的单据，无任一权限返回 403。"""
        kinds = [kind for kind in ("purchase_in", "purchase_return", "sale_out", "sale_return") if self.allowed(f"module_inventory:{kind}:query")]
        if not kinds:
            raise CustomException(msg="无权限查看最近单据", status_code=403)
        return [RecentDocument.model_validate(row) for row in await self.crud.recent(self.auth, kinds, limit)]

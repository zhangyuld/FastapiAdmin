from decimal import Decimal
from typing import Any

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Subquery

from app.core.exceptions import CustomException
from app.modules.inventory.basic.model import GoodsCategoryModel, GoodsModel, WarehouseModel
from app.modules.inventory.stock.model import StockBalanceModel, StockLogModel

from .schema import StockReportQuery


class StockReportCRUD:
    """库存报表为企业共享只读查询，不按创建人截断余额或流水。"""

    def __init__(self, db: AsyncSession) -> None:
        """只绑定数据库会话，不继承可写通用 CRUD。"""
        self.db = db

    @staticmethod
    def _warning() -> ColumnElement[str]:
        """与当前库存一致：严格低于下限、严格高于正上限，其余正常。"""
        return case(
            (StockBalanceModel.quantity < GoodsModel.stock_min, "low"),
            ((GoodsModel.stock_max > 0) & (StockBalanceModel.quantity > GoodsModel.stock_max), "high"),
            else_="normal",
        )

    @staticmethod
    def _scope(query: StockReportQuery) -> Select:
        """只过滤库存记录，不因当前档案停用或软删除丢失库存业务。"""
        model = StockBalanceModel if query.view == "balance" else StockLogModel
        conditions = [model.is_deleted.is_(False)]
        for value, column in ((query.warehouse_id, model.warehouse_id), (query.category_id, GoodsModel.category_id)):
            if value is not None:
                conditions.append(column == value)
        for value, column in (
            (query.warehouse_name, WarehouseModel.warehouse_name),
            (query.category_name, GoodsCategoryModel.name),
            (query.goods_code, GoodsModel.goods_code),
            (query.goods_name, GoodsModel.goods_name),
        ):
            if value:
                conditions.append(column.contains(value, autoescape=True))
        if query.business_date:
            conditions.append(StockLogModel.business_date.between(*query.business_date))
        if query.warning:
            conditions.append(StockReportCRUD._warning() == query.warning)
        dimensions = [
            model.warehouse_id.label("warehouse_id"),
            model.goods_id.label("goods_id"),
            WarehouseModel.warehouse_name.label("warehouse_name"),
            GoodsModel.goods_code.label("goods_code"),
            GoodsModel.goods_name.label("goods_name"),
            GoodsModel.spec.label("spec"),
            GoodsModel.unit.label("unit"),
        ]
        measures = [model.quantity, model.avg_cost, model.stock_amount, StockReportCRUD._warning().label("warning")] if query.view == "balance" else [model.change_quantity, model.cost_amount]
        return (
            select(*dimensions, *measures)
            .select_from(model)
            .join(GoodsModel, GoodsModel.id == model.goods_id)
            .join(WarehouseModel, WarehouseModel.id == model.warehouse_id)
            .outerjoin(GoodsCategoryModel, GoodsCategoryModel.id == GoodsModel.category_id)
            .where(*conditions)
        )

    @staticmethod
    def _positive(column: ColumnElement[Decimal]) -> ColumnElement[Decimal]:
        """正数累计为入库，免费商品的数量和零数量成本调整互不丢失。"""
        return case((column > 0, column), else_=Decimal("0"))

    @staticmethod
    def _negative(column: ColumnElement[Decimal]) -> ColumnElement[Decimal]:
        """负数取绝对值累计为出库，不按原业务类型猜测反向流水方向。"""
        return case((column < 0, -column), else_=Decimal("0"))

    @classmethod
    def _grouped(cls, query: StockReportQuery) -> Subquery:
        """余额保留现有零记录，流水按当前仓库商品档案分组且保留净零组。"""
        lines = cls._scope(query).subquery("stock_report_lines")
        if query.view == "balance":
            return lines
        columns = lines.c
        dimensions = [columns[field] for field in ("warehouse_id", "goods_id", "warehouse_name", "goods_code", "goods_name", "spec", "unit")]
        return (
            select(
                *dimensions,
                func.sum(cls._positive(columns.change_quantity)).label("in_quantity"),
                func.sum(cls._negative(columns.change_quantity)).label("out_quantity"),
                func.sum(columns.change_quantity).label("net_quantity"),
                func.sum(cls._positive(columns.cost_amount)).label("in_amount"),
                func.sum(cls._negative(columns.cost_amount)).label("out_amount"),
                func.sum(columns.cost_amount).label("net_amount"),
            )
            .group_by(*dimensions)
            .subquery("stock_report_groups")
        )

    @staticmethod
    def _order(grouped: Subquery, order_by: list[dict[str, str]] | None) -> list[ColumnElement[Any]]:
        """排序字段与方向白名单校验，追加仓库商品键保证分页稳定。"""
        if order_by is not None and not isinstance(order_by, list):
            raise CustomException(msg="排序必须为数组", status_code=422)
        orders = []
        for mapping in order_by or [{"goods_code": "asc"}]:
            if not isinstance(mapping, dict) or not mapping:
                raise CustomException(msg="排序格式无效", status_code=422)
            for field, direction in mapping.items():
                if field not in set(grouped.c.keys()) | {"id"} or not isinstance(direction, str) or direction.lower() not in {"asc", "desc"}:
                    raise CustomException(msg="排序字段或方向无效", status_code=422)
                column = grouped.c["goods_id" if field == "id" else field]
                orders.append(column.asc() if direction.lower() == "asc" else column.desc())
        return orders + [grouped.c.warehouse_id.asc(), grouped.c.goods_id.asc()]

    async def rows(self, query: StockReportQuery, page_no: int | None = None, page_size: int = 10, order_by: list[dict[str, str]] | None = None) -> tuple[list[dict[str, Any]], int]:
        """分组后分页，导出使用相同筛选并受服务层行数上限约束。"""
        grouped = self._grouped(query)
        ordering = self._order(grouped, order_by)
        total = await self.db.scalar(select(func.count()).select_from(grouped)) or 0
        statement = select(grouped).order_by(*ordering)
        if page_no is not None:
            statement = statement.offset((page_no - 1) * page_size).limit(page_size)
        return [dict(row) for row in (await self.db.execute(statement)).mappings().all()], total

    async def summary(self, query: StockReportQuery) -> dict[str, Any]:
        """对完整筛选分组汇总金额，商品跨仓库去重，不汇总混合单位数量。"""
        grouped = self._grouped(query)
        columns = grouped.c
        count = func.count(func.distinct(columns.goods_id)).label("goods_count")
        measures = (
            [func.coalesce(func.sum(columns.stock_amount), 0).label("stock_amount")]
            if query.view == "balance"
            else [func.coalesce(func.sum(columns[field]), 0).label(field) for field in ("in_amount", "out_amount", "net_amount")]
        )
        return dict((await self.db.execute(select(count, *measures).select_from(grouped))).mappings().one())

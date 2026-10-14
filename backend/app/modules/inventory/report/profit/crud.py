from typing import Any

from sqlalchemy import LargeBinary, Select, String, case, cast, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Subquery

from app.core.exceptions import CustomException
from app.modules.inventory.basic.model import CustomerModel, GoodsCategoryModel, GoodsModel, WarehouseModel
from app.modules.inventory.sale.model import SaleOutItemModel, SaleOutModel, SaleReturnItemModel, SaleReturnModel

from ..sale_allocation import allocated_sale_amounts
from .schema import ProfitReportQuery


class ProfitReportCRUD:
    """毛利只读统计，成本取已确认明细，不读取当前参考进价或重复扣冲销。"""

    def __init__(self, db: AsyncSession) -> None:
        """绑定企业共享查询会话，不继承通用写入能力。"""
        self.db = db

    @staticmethod
    def _branch(query: ProfitReportQuery, is_return: bool) -> Select:
        """每条有效销售明细一行，商品筛选先于单据和商品分组。"""
        document = SaleReturnModel if is_return else SaleOutModel
        item = SaleReturnItemModel if is_return else SaleOutItemModel
        parent_id = item.sale_return_id if is_return else item.sale_out_id
        kind = "sale_return" if is_return else "sale_out"
        conditions = [document.status == 1, document.is_deleted.is_(False), item.is_deleted.is_(False)]
        if query.business_date:
            conditions.append(document.business_date.between(*query.business_date))
        for value, column in ((query.warehouse_id, document.warehouse_id), (query.category_id, GoodsModel.category_id)):
            if value is not None:
                conditions.append(column == value)
        for value, column in (
            (query.business_no, document.order_no),
            (query.customer_name, CustomerModel.customer_name),
            (query.warehouse_name, WarehouseModel.warehouse_name),
            (query.category_name, GoodsCategoryModel.name),
            (query.goods_code, item.goods_code),
            (query.goods_name, item.goods_name),
        ):
            if value:
                conditions.append(column.contains(value, autoescape=True))
        matched_documents = (
            select(document.id)
            .select_from(document)
            .join(item, parent_id == document.id)
            .join(CustomerModel, CustomerModel.id == document.customer_id)
            .join(WarehouseModel, WarehouseModel.id == document.warehouse_id)
            .outerjoin(GoodsModel, GoodsModel.id == item.goods_id)
            .outerjoin(GoodsCategoryModel, GoodsCategoryModel.id == GoodsModel.category_id)
            .where(*conditions)
            .correlate(None)
        )
        allocated = None if is_return else allocated_sale_amounts(matched_documents)
        statement = (
            select(
                literal(kind, type_=String(32)).label("business_type"),
                document.id.label("business_id"),
                document.order_no.label("business_no"),
                document.business_date.label("business_date"),
                document.customer_id.label("customer_id"),
                CustomerModel.customer_name.label("customer_name"),
                document.warehouse_id.label("warehouse_id"),
                WarehouseModel.warehouse_name.label("warehouse_name"),
                item.goods_id.label("goods_id"),
                item.goods_code.label("goods_code"),
                item.goods_name.label("goods_name"),
                item.spec.label("spec"),
                item.unit.label("unit"),
                (-item.line_amount if is_return else allocated.c.sale_amount).label("net_sale_amount"),
                (-item.cost_amount if is_return else item.cost_amount).label("net_cost_amount"),
                case((item.cost_amount.is_(None), 1), else_=0).label("cost_missing"),
            )
            .select_from(document)
            .join(item, parent_id == document.id)
            .join(CustomerModel, CustomerModel.id == document.customer_id)
            .join(WarehouseModel, WarehouseModel.id == document.warehouse_id)
            .outerjoin(GoodsModel, GoodsModel.id == item.goods_id)
            .outerjoin(GoodsCategoryModel, GoodsCategoryModel.id == GoodsModel.category_id)
            .where(*conditions)
        )
        return statement if is_return else statement.join(allocated, allocated.c.id == item.id)

    def _lines(self, query: ProfitReportQuery) -> Subquery:
        """收入及固化成本均按各单自身业务日期带方向合并。"""
        return union_all(self._branch(query, False), self._branch(query, True)).subquery("profit_report_lines")

    async def _assert_costs(self, lines: Subquery) -> None:
        """命中筛选任一有效明细缺失成本时，拒绝整个结果，不伪造零成本。"""
        missing = await self.db.scalar(select(lines.c.business_no).where(lines.c.cost_missing == 1).limit(1))
        if missing is not None:
            raise CustomException(msg=f"单据 {missing} 缺少固化成本金额，无法计算毛利", status_code=409)

    @staticmethod
    def _grouped(lines: Subquery, view: str) -> Subquery:
        """单据按类型与 ID，商品按仓库和完整快照分组，成本不静默补零。"""
        columns = lines.c
        if view == "documents":
            dimensions = [
                columns.business_type,
                columns.business_id,
                columns.business_no,
                columns.business_date,
                columns.customer_id,
                columns.customer_name,
                columns.warehouse_id,
                columns.warehouse_name,
            ]
            extra = [(columns.business_type + literal(":") + cast(columns.business_id, String(20))).label("id")]
        else:
            dimensions = [columns.goods_id, columns.warehouse_id, columns.warehouse_name, columns.goods_code, columns.goods_name, columns.spec, columns.unit]
            dimensions += [cast(columns[field], LargeBinary).label("snapshot_" + field) for field in ("goods_code", "goods_name", "spec", "unit")]
            extra = []
        amounts = (
            select(
                *dimensions,
                *extra,
                func.sum(columns.net_sale_amount).label("net_sale_amount"),
                func.sum(columns.net_cost_amount).label("net_cost_amount"),
            )
            .group_by(*dimensions)
            .subquery("profit_amount_groups")
        )
        profit = amounts.c.net_sale_amount - amounts.c.net_cost_amount
        # 数据库比例只用于排序，响应与导出采用服务层 Decimal 精确舍入。
        margin_order = case((amounts.c.net_sale_amount > 0, profit * 100 / func.nullif(amounts.c.net_sale_amount, 0)), else_=None)
        return select(amounts, profit.label("gross_profit"), margin_order.label("margin_order")).subquery("profit_report_groups")

    @staticmethod
    def _order(grouped: Subquery, view: str, order_by: list[dict[str, str]] | None) -> list[ColumnElement[Any]]:
        """白名单排序追加稳定分组键，毛利率允许空值且不作为计算来源。"""
        stable = (
            ["business_type", "business_id"]
            if view == "documents"
            else ["goods_id", "warehouse_id", "goods_code", "goods_name", "spec", "unit", "snapshot_goods_code", "snapshot_goods_name", "snapshot_spec", "snapshot_unit"]
        )
        allowed = {field for field in grouped.c.keys() if not field.startswith("snapshot_") and field != "margin_order"} | {"id", "gross_margin"}
        if order_by is not None and not isinstance(order_by, list):
            raise CustomException(msg="排序必须为数组", status_code=422)
        orders = []
        for mapping in order_by or [{"business_date" if view == "documents" else "goods_code": "desc" if view == "documents" else "asc"}]:
            if not isinstance(mapping, dict) or not mapping:
                raise CustomException(msg="排序格式无效", status_code=422)
            for field, direction in mapping.items():
                if field not in allowed or not isinstance(direction, str) or direction.lower() not in {"asc", "desc"}:
                    raise CustomException(msg="排序字段或方向无效", status_code=422)
                key = "margin_order" if field == "gross_margin" else "goods_id" if view == "goods" and field == "id" else field
                orders.append(grouped.c[key].asc() if direction.lower() == "asc" else grouped.c[key].desc())
        return orders + [grouped.c[field].asc() for field in stable]

    async def rows(self, query: ProfitReportQuery, page_no: int | None = None, page_size: int = 10, order_by: list[dict[str, str]] | None = None) -> tuple[list[dict[str, Any]], int]:
        """校验全部筛选成本后分组分页，不只检查当前页或导出截取部分。"""
        lines = self._lines(query)
        grouped = self._grouped(lines, query.view)
        order = self._order(grouped, query.view, order_by)
        await self._assert_costs(lines)
        total = await self.db.scalar(select(func.count()).select_from(grouped)) or 0
        statement = select(grouped).order_by(*order)
        if page_no is not None:
            statement = statement.offset((page_no - 1) * page_size).limit(page_size)
        return [dict(row) for row in (await self.db.execute(statement)).mappings().all()], total

    async def summary(self, query: ProfitReportQuery) -> dict[str, Any]:
        """完整筛选汇总收入和成本，成本检查在 SUM 忽略 NULL 之前执行。"""
        lines = self._lines(query)
        await self._assert_costs(lines)
        statement = select(
            func.coalesce(func.sum(lines.c.net_sale_amount), 0).label("net_sale_amount"),
            func.coalesce(func.sum(lines.c.net_cost_amount), 0).label("net_cost_amount"),
        ).select_from(lines)
        return dict((await self.db.execute(statement)).mappings().one())

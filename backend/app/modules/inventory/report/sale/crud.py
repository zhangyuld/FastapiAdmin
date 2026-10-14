from decimal import Decimal
from typing import Any

from sqlalchemy import LargeBinary, Numeric, Select, String, cast, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Subquery

from app.core.exceptions import CustomException
from app.modules.inventory.basic.model import CustomerModel, GoodsCategoryModel, GoodsModel, WarehouseModel
from app.modules.inventory.sale.model import SaleOutItemModel, SaleOutModel, SaleReturnItemModel, SaleReturnModel

from ..sale_allocation import allocated_sale_amounts
from .schema import SaleReportQuery


class SaleReportCRUD:
    """销售报表为企业共享只读统计，不按业务创建人截断出库与退货。"""

    def __init__(self, db: AsyncSession) -> None:
        """只绑定数据库会话，不继承通用写入 CRUD。"""
        self.db = db

    @staticmethod
    def _allocated(document_ids: Select | None = None) -> Subquery:
        """复用报表模块内的累计优惠分摊，保持原销售查询与测试入口兼容。"""
        return allocated_sale_amounts(document_ids)

    @staticmethod
    def _branch(query: SaleReportQuery, is_return: bool) -> Select:
        """每条有效销售明细一行，商品筛选先于单据和商品分组。"""
        document = SaleReturnModel if is_return else SaleOutModel
        item = SaleReturnItemModel if is_return else SaleOutItemModel
        parent_id = item.sale_return_id if is_return else item.sale_out_id
        kind = "sale_return" if is_return else "sale_out"
        money_zero = literal(Decimal("0.00"), type_=Numeric(18, 2))
        quantity_zero = literal(Decimal("0.000"), type_=Numeric(18, 3))
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
        allocated = None if is_return else SaleReportCRUD._allocated(matched_documents)
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
                (money_zero if is_return else allocated.c.sale_amount).label("sale_amount"),
                (item.line_amount if is_return else money_zero).label("return_amount"),
                (quantity_zero if is_return else item.quantity).label("sale_quantity"),
                (item.quantity if is_return else quantity_zero).label("return_quantity"),
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

    def _lines(self, query: SaleReportQuery) -> Subquery:
        """出库及退货都按自身日期选取，不关联原出库日期或重复扣除冲销账单。"""
        return union_all(self._branch(query, False), self._branch(query, True)).subquery("sale_report_lines")

    @staticmethod
    def _grouped(lines: Subquery, view: str) -> Subquery:
        """单据按类型和 ID 分组，商品按仓库、商品与快照分组。"""
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
            # 二进制键防止 MySQL 默认不区分大小写的排序规则合并不同快照。
            dimensions += [cast(columns[field], LargeBinary).label("snapshot_" + field) for field in ("goods_code", "goods_name", "spec", "unit")]
            extra = [
                func.sum(columns.sale_quantity).label("sale_quantity"),
                func.sum(columns.return_quantity).label("return_quantity"),
                (func.sum(columns.sale_quantity) - func.sum(columns.return_quantity)).label("net_quantity"),
            ]
        return (
            select(
                *dimensions,
                *extra,
                func.sum(columns.sale_amount).label("sale_amount"),
                func.sum(columns.return_amount).label("return_amount"),
                (func.sum(columns.sale_amount) - func.sum(columns.return_amount)).label("net_sale_amount"),
            )
            .group_by(*dimensions)
            .subquery("sale_report_groups")
        )

    @staticmethod
    def _order(grouped: Subquery, view: str, order_by: list | None) -> list[Any]:
        """校验排序白名单并补稳定分组键，防止分页重复和 SQL 拼接。"""
        stable = ["business_type", "business_id"] if view == "documents" else ["goods_id", "warehouse_id", "goods_code", "goods_name", "spec", "unit"]
        if view == "goods":
            stable += ["snapshot_goods_code", "snapshot_goods_name", "snapshot_spec", "snapshot_unit"]
        orders = []
        if order_by is not None and not isinstance(order_by, list):
            raise CustomException(msg="排序必须为数组", status_code=422)
        allowed = {field for field in grouped.c.keys() if not field.startswith("snapshot_")}
        for mapping in order_by or [{"business_date" if view == "documents" else "goods_code": "desc" if view == "documents" else "asc"}]:
            if not isinstance(mapping, dict) or not mapping:
                raise CustomException(msg="排序格式无效", status_code=422)
            for field, direction in mapping.items():
                if not isinstance(direction, str) or direction.lower() not in {"asc", "desc"} or field not in allowed | {"id"}:
                    raise CustomException(msg="排序字段或方向无效", status_code=422)
                column = grouped.c["goods_id" if view == "goods" and field == "id" else field]
                orders.append(column.asc() if direction.lower() == "asc" else column.desc())
        return orders + [grouped.c[field].asc() for field in stable]

    async def rows(self, query: SaleReportQuery, page_no: int | None = None, page_size: int = 10, order_by: list | None = None) -> tuple[list[dict], int]:
        """查询分组后再分页，导出复用同一明细筛选且不分页。"""
        grouped = self._grouped(self._lines(query), query.view)
        total = await self.db.scalar(select(func.count()).select_from(grouped)) or 0
        statement = select(grouped).order_by(*self._order(grouped, query.view, order_by))
        if page_no is not None:
            statement = statement.offset((page_no - 1) * page_size).limit(page_size)
        return [dict(row) for row in (await self.db.execute(statement)).mappings().all()], total

    async def summary(self, query: SaleReportQuery) -> dict:
        """金额从有效明细汇总，单据按类型及 ID 去重，排除分页和行数重复。"""
        lines = self._lines(query)
        documents = select(lines.c.business_type, lines.c.business_id).distinct().subquery()
        sale = func.coalesce(func.sum(lines.c.sale_amount), 0)
        returned = func.coalesce(func.sum(lines.c.return_amount), 0)
        statement = select(
            select(func.count()).select_from(documents).scalar_subquery().label("document_count"),
            sale.label("sale_amount"),
            returned.label("return_amount"),
            (sale - returned).label("net_sale_amount"),
        ).select_from(lines)
        return dict((await self.db.execute(statement)).mappings().one())

from decimal import Decimal
from typing import Any

from sqlalchemy import LargeBinary, Numeric, Select, String, cast, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Subquery

from app.core.exceptions import CustomException
from app.modules.inventory.basic.model import GoodsCategoryModel, GoodsModel, SupplierModel, WarehouseModel
from app.modules.inventory.purchase.model import PurchaseInItemModel, PurchaseInModel, PurchaseReturnItemModel, PurchaseReturnModel

from .schema import PurchaseReportQuery


class PurchaseReportCRUD:
    """采购报表为企业共享只读统计，不按业务创建人截断入库与退货。"""

    def __init__(self, db: AsyncSession) -> None:
        """只绑定数据库会话，不继承通用写入 CRUD。"""
        self.db = db

    @staticmethod
    def _branch(query: PurchaseReportQuery, is_return: bool) -> Select:
        """每条有效采购明细一行，商品筛选先于单据和商品分组。"""
        document = PurchaseReturnModel if is_return else PurchaseInModel
        item = PurchaseReturnItemModel if is_return else PurchaseInItemModel
        parent_id = item.purchase_return_id if is_return else item.purchase_in_id
        kind = "purchase_return" if is_return else "purchase_in"
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
            (query.supplier_name, SupplierModel.supplier_name),
            (query.warehouse_name, WarehouseModel.warehouse_name),
            (query.category_name, GoodsCategoryModel.name),
            (query.goods_code, item.goods_code),
            (query.goods_name, item.goods_name),
        ):
            if value:
                conditions.append(column.contains(value, autoescape=True))
        return (
            select(
                literal(kind, type_=String(32)).label("business_type"),
                document.id.label("business_id"),
                document.order_no.label("business_no"),
                document.business_date.label("business_date"),
                document.supplier_id.label("supplier_id"),
                SupplierModel.supplier_name.label("supplier_name"),
                document.warehouse_id.label("warehouse_id"),
                WarehouseModel.warehouse_name.label("warehouse_name"),
                item.goods_id.label("goods_id"),
                item.goods_code.label("goods_code"),
                item.goods_name.label("goods_name"),
                item.spec.label("spec"),
                item.unit.label("unit"),
                (money_zero if is_return else item.line_amount).label("purchase_amount"),
                (item.line_amount if is_return else money_zero).label("return_amount"),
                (quantity_zero if is_return else item.quantity).label("purchase_quantity"),
                (item.quantity if is_return else quantity_zero).label("return_quantity"),
            )
            .select_from(document)
            .join(item, parent_id == document.id)
            .join(SupplierModel, SupplierModel.id == document.supplier_id)
            .join(WarehouseModel, WarehouseModel.id == document.warehouse_id)
            .outerjoin(GoodsModel, GoodsModel.id == item.goods_id)
            .outerjoin(GoodsCategoryModel, GoodsCategoryModel.id == GoodsModel.category_id)
            .where(*conditions)
        )

    def _lines(self, query: PurchaseReportQuery) -> Subquery:
        """入库及退货都按自身日期选取，不关联原入库日期或重复扣除冲销账单。"""
        return union_all(self._branch(query, False), self._branch(query, True)).subquery("purchase_report_lines")

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
                columns.supplier_id,
                columns.supplier_name,
                columns.warehouse_id,
                columns.warehouse_name,
            ]
            extra = [(columns.business_type + literal(":") + cast(columns.business_id, String(20))).label("id")]
        else:
            dimensions = [columns.goods_id, columns.warehouse_id, columns.warehouse_name, columns.goods_code, columns.goods_name, columns.spec, columns.unit]
            # 二进制键防止 MySQL 默认不区分大小写的排序规则合并不同快照。
            dimensions += [cast(columns[field], LargeBinary).label("snapshot_" + field) for field in ("goods_code", "goods_name", "spec", "unit")]
            extra = [
                func.sum(columns.purchase_quantity).label("purchase_quantity"),
                func.sum(columns.return_quantity).label("return_quantity"),
                (func.sum(columns.purchase_quantity) - func.sum(columns.return_quantity)).label("net_quantity"),
            ]
        return (
            select(
                *dimensions,
                *extra,
                func.sum(columns.purchase_amount).label("purchase_amount"),
                func.sum(columns.return_amount).label("return_amount"),
                (func.sum(columns.purchase_amount) - func.sum(columns.return_amount)).label("net_purchase_amount"),
            )
            .group_by(*dimensions)
            .subquery("purchase_report_groups")
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

    async def rows(self, query: PurchaseReportQuery, page_no: int | None = None, page_size: int = 10, order_by: list | None = None) -> tuple[list[dict], int]:
        """查询分组后再分页，导出复用同一明细筛选且不分页。"""
        grouped = self._grouped(self._lines(query), query.view)
        total = await self.db.scalar(select(func.count()).select_from(grouped)) or 0
        statement = select(grouped).order_by(*self._order(grouped, query.view, order_by))
        if page_no is not None:
            statement = statement.offset((page_no - 1) * page_size).limit(page_size)
        return [dict(row) for row in (await self.db.execute(statement)).mappings().all()], total

    async def summary(self, query: PurchaseReportQuery) -> dict:
        """金额从有效明细汇总，单据按类型及 ID 去重，排除分页和行数重复。"""
        lines = self._lines(query)
        documents = select(lines.c.business_type, lines.c.business_id).distinct().subquery()
        purchase = func.coalesce(func.sum(lines.c.purchase_amount), 0)
        returned = func.coalesce(func.sum(lines.c.return_amount), 0)
        statement = select(
            select(func.count()).select_from(documents).scalar_subquery().label("document_count"),
            purchase.label("purchase_amount"),
            returned.label("return_amount"),
            (purchase - returned).label("net_purchase_amount"),
        ).select_from(lines)
        return dict((await self.db.execute(statement)).mappings().one())

from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.modules.inventory.basic.model import GoodsModel, WarehouseModel

from .model import StockBalanceModel, StockLogModel
from .query_schema import BalanceQuery, LogQuery


class StockQueryCRUD(CRUDBase):
    """企业共享余额和不可变流水的只读访问，不提供通用修改入口。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession, kind: Literal["balance", "log"]) -> None:
        """查询权限在控制器验证，关闭创建人数据范围隔离。"""
        self.kind = kind
        super().__init__(StockBalanceModel if kind == "balance" else StockLogModel, auth, db, enforce_data_scope=False)

    async def rows(
        self, query: BalanceQuery | LogQuery, page_no: int | None = None, page_size: int = 10, id: int | None = None, order_by: list[dict[str, str]] | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """使用结构化条件联查名称，历史流水不因档案停用而隐藏。"""
        model = self.model
        conditions = [model.is_deleted.is_(False)]
        for name in ("goods_id", "warehouse_id", "created_id", "updated_id"):
            value = getattr(query, name, None)
            if value is not None:
                conditions.append(getattr(model, name) == value)
        for name, column in (("goods_code", GoodsModel.goods_code), ("goods_name", GoodsModel.goods_name), ("warehouse_name", WarehouseModel.warehouse_name)):
            value = getattr(query, name, None)
            if value and value.strip():
                conditions.append(column.contains(value.strip(), autoescape=True))
        if query.category_id is not None:
            conditions.append(GoodsModel.category_id == query.category_id)
        for name in ("created_time", "updated_time"):
            bounds = getattr(query, name, None)
            if bounds:
                if len(bounds) != 2 or bounds[0] > bounds[1]:
                    raise CustomException(msg="审计时间区间无效", status_code=422)
                conditions.append(getattr(model, name).between(*bounds))
        if id is not None:
            conditions.append(model.id == id)
        if isinstance(query, BalanceQuery):
            if query.quantity_state:
                conditions.append(model.quantity > 0 if query.quantity_state == "positive" else model.quantity == 0)
            if query.warning == "low":
                conditions.append(model.quantity < GoodsModel.stock_min)
            if query.warning == "high":
                conditions.extend([GoodsModel.stock_max > 0, model.quantity > GoodsModel.stock_max])
        else:
            for name in ("business_type", "operation_type"):
                if getattr(query, name) is not None:
                    conditions.append(getattr(model, name) == getattr(query, name))
            if query.business_no and query.business_no.strip():
                conditions.append(model.business_no.contains(query.business_no.strip(), autoescape=True))
            for name in ("business_date", "posted_time"):
                bounds = getattr(query, name)
                if bounds:
                    conditions.append(getattr(model, name).between(*bounds))
        statement = (
            select(model, GoodsModel, WarehouseModel.warehouse_name).join(GoodsModel, GoodsModel.id == model.goods_id).join(WarehouseModel, WarehouseModel.id == model.warehouse_id).where(*conditions)
        )
        total = await self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        order = []
        for mapping in order_by or [{"id": "desc"}]:
            if not isinstance(mapping, dict):
                raise CustomException(msg="排序格式无效", status_code=422)
            for name, direction in mapping.items():
                if name not in model.__table__.columns or not isinstance(direction, str) or direction.lower() not in {"asc", "desc"}:
                    raise CustomException(msg="排序字段或方向无效", status_code=422)
                column = getattr(model, name)
                order.append(column.asc() if direction.lower() == "asc" else column.desc())
        statement = statement.options(selectinload(model.created_by), selectinload(model.updated_by)).order_by(*order, model.id.desc())
        if page_no is not None:
            statement = statement.offset((page_no - 1) * page_size).limit(page_size)
        result = []
        for item, goods, warehouse_name in (await self.db.execute(statement)).all():
            values = {column.key: getattr(item, column.key) for column in model.__table__.columns}
            values.update(
                warehouse_name=warehouse_name,
                goods_code=goods.goods_code,
                goods_name=goods.goods_name,
                category_id=goods.category_id,
                spec=goods.spec,
                unit=goods.unit,
                created_by=item.created_by,
                updated_by=item.updated_by,
            )
            if self.kind == "balance":
                warning = "low" if item.quantity < goods.stock_min else "high" if goods.stock_max > 0 and item.quantity > goods.stock_max else "normal"
                values.update(stock_min=goods.stock_min, stock_max=goods.stock_max, warning=warning)
            result.append(values)
        return result, total

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException

from .model import StockCheckItemModel, StockCheckModel, StockOpeningItemModel, StockOpeningModel

Document = StockOpeningModel | StockCheckModel
Item = StockOpeningItemModel | StockCheckItemModel


class StockDocumentCRUD(CRUDBase):
    """库存模块内期初及盘点主从表访问，保留单据数据范围和请求事务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession, kind: Literal["opening", "check"]) -> None:
        """仅在库存模块内按单据种类配置模型及外键。"""
        self.kind = kind
        self.item_model = StockOpeningItemModel if kind == "opening" else StockCheckItemModel
        self.parent_field = "stock_opening_id" if kind == "opening" else "stock_check_id"
        self.number_field = "opening_no" if kind == "opening" else "check_no"
        super().__init__(StockOpeningModel if kind == "opening" else StockCheckModel, auth, db)

    async def document(self, id: int, lock: bool = False) -> Document:
        """授权后读取主单，锁定不联查用户以缩小 MySQL 排他锁范围。"""
        statement = (
            select(self.model).where(*(await self._build_conditions(id=id))).options(selectinload(self.model.created_by), selectinload(self.model.updated_by)).execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update(of=self.model)
        document = (await self.db.execute(statement)).scalars().first()
        if document is None:
            raise CustomException(msg="单据不存在或无权访问", status_code=404)
        return document

    async def items(self, id: int, lock: bool = False) -> Sequence[Item]:
        """明细只经已授权主单访问，并按商品顺序加锁。"""
        statement = select(self.item_model).where(getattr(self.item_model, self.parent_field) == id, self.item_model.is_deleted.is_(False)).order_by(self.item_model.goods_id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return (await self.db.execute(statement)).scalars().all()

    async def add_items(self, id: int, rows: list[dict[str, Any]]) -> None:
        """批量写入带审计用户的库存商品快照。"""
        self.db.add_all([self.item_model(**{self.parent_field: id}, **row, created_id=self.auth.user.id, updated_id=self.auth.user.id) for row in rows])
        await self.db.flush()

    async def replace(self, document: Document, values: dict[str, Any], rows: list[dict[str, Any]]) -> None:
        """原子匹配草稿版本后替换明细，不允许覆盖已确认单据。"""
        await self.cas(document, values, expected_status=0)
        await self.db.execute(delete(self.item_model).where(getattr(self.item_model, self.parent_field) == document.id))
        await self.add_items(document.id, rows)

    async def cas(self, document: Document, values: dict[str, Any], expected_status: int) -> None:
        """并发状态与版本冲突使整笔请求事务回滚。"""
        conditions = await self._build_conditions(id=document.id, status=expected_status, version=document.version)
        result = await self.db.execute(
            update(self.model)
            .where(*conditions)
            .values(**values, version=document.version + 1, updated_id=self.auth.user.id, updated_time=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise CustomException(msg="单据版本或状态已变化，请刷新重试", status_code=409)

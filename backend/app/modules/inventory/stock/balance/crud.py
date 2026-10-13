from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema

from ..query_crud import StockQueryCRUD


class StockBalanceCRUD(StockQueryCRUD):
    """当前库存数据访问边界。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """绑定当前库存模型和数据范围。"""
        super().__init__(auth, db, "balance")

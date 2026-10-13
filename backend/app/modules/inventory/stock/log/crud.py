from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema

from ..query_crud import StockQueryCRUD


class StockLogCRUD(StockQueryCRUD):
    """库存流水数据访问边界。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """绑定库存流水模型和数据范围。"""
        super().__init__(auth, db, "log")

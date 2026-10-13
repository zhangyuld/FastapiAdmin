from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema

from ..query_service import StockQueryService
from .crud import StockBalanceCRUD


class StockBalanceService(StockQueryService):
    """当前库存只读查询业务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """绑定业务配置及模块内数据访问层。"""
        super().__init__(auth, db, "balance")
        self.crud = StockBalanceCRUD(auth, db)

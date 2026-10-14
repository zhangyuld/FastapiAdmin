from sqlalchemy.ext.asyncio import AsyncSession

from ..query_crud import FinanceQueryCRUD


class PayableQueryCRUD(FinanceQueryCRUD):
    """应付账款只读账单和对象余额访问。"""

    def __init__(self, db: AsyncSession) -> None:
        """固定业务模型，避免应收与应付筛选串用。"""
        super().__init__(db, "payable")

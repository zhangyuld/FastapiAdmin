from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema

from ..query_service import FinanceQueryService
from .crud import ReceivableQueryCRUD


class ReceivableQueryService(FinanceQueryService):
    """应收账款查询、追溯和余额导出业务，不替代既有记账服务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """绑定应收账款查询模型，记账由 posting.py 保持原契约。"""
        super().__init__(auth, db, "receivable")
        self.crud = ReceivableQueryCRUD(db)

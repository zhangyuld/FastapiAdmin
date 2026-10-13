from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema

from ..document_service import StockDocumentService
from .crud import StockOpeningCRUD


class StockOpeningService(StockDocumentService):
    """期初库存草稿及确认冲销业务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """绑定业务配置及模块内数据访问层。"""
        super().__init__(auth, db, "opening")
        self.crud = StockOpeningCRUD(auth, db)

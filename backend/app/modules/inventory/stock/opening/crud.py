from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema

from ..document_crud import StockDocumentCRUD


class StockOpeningCRUD(StockDocumentCRUD):
    """期初库存数据访问边界。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """绑定期初库存模型和数据范围。"""
        super().__init__(auth, db, "opening")

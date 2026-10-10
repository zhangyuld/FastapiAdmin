from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from ..model import SupplierModel
from .schema import SupplierCreateSchema, SupplierUpdateSchema


class SupplierCRUD(CRUDBase[SupplierModel, SupplierCreateSchema, SupplierUpdateSchema]):
    """供应商数据访问层，供应商档案不按创建人隔离。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=SupplierModel, auth=auth, db=db, enforce_data_scope=False)

    async def get_by_code(self, supplier_code: str) -> SupplierModel | None:
        """按供应商编码查询未删除供应商。"""
        return await self.get(supplier_code=supplier_code)

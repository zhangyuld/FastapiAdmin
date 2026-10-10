from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from ..model import WarehouseModel
from .schema import WarehouseCreateSchema, WarehouseUpdateSchema


class WarehouseCRUD(CRUDBase[WarehouseModel, WarehouseCreateSchema, WarehouseUpdateSchema]):
    """仓库数据访问层，仓库档案不按创建人隔离。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=WarehouseModel, auth=auth, db=db, enforce_data_scope=False)

    async def get_by_code(self, warehouse_code: str) -> WarehouseModel | None:
        """按仓库编码查询仓库，包含已软删除数据以保护唯一约束。"""
        return await self.get(warehouse_code=warehouse_code, include_deleted=True)

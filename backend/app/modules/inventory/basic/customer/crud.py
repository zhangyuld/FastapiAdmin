from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from ..model import CustomerModel
from .schema import CustomerCreateSchema, CustomerUpdateSchema


class CustomerCRUD(CRUDBase[CustomerModel, CustomerCreateSchema, CustomerUpdateSchema]):
    """客户数据访问层，客户档案不按创建人隔离。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=CustomerModel, auth=auth, db=db, enforce_data_scope=False)

    async def get_by_code(self, customer_code: str) -> CustomerModel | None:
        """按客户编码查询客户，包含已软删除数据以保护唯一约束。"""
        return await self.get(customer_code=customer_code, include_deleted=True)

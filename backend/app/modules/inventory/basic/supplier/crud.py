from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema, PageResultSchema

from ..model import SupplierModel
from ..option_schema import ArchiveOptionQuery
from .schema import SupplierCreateSchema, SupplierOptionSchema, SupplierUpdateSchema


class SupplierCRUD(CRUDBase[SupplierModel, SupplierCreateSchema, SupplierUpdateSchema]):
    """供应商数据访问层，供应商档案不按创建人隔离。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=SupplierModel, auth=auth, db=db, enforce_data_scope=False)

    async def options(self, query: ArchiveOptionQuery) -> PageResultSchema[SupplierOptionSchema]:
        """仅查询下拉必要列，沿用软删除及共享档案范围，不加载用户关系。"""
        conditions = await self._build_conditions(status=query.status)
        if query.keyword:
            conditions.append(or_(SupplierModel.supplier_code.contains(query.keyword, autoescape=True), SupplierModel.supplier_name.contains(query.keyword, autoescape=True)))
        total = await self.db.scalar(select(func.count()).select_from(SupplierModel).where(*conditions)) or 0
        statement = select(SupplierModel.id, SupplierModel.supplier_code, SupplierModel.supplier_name, SupplierModel.status).where(*conditions).order_by(SupplierModel.id.asc())
        result = await self.db.execute(statement.offset((query.page_no - 1) * query.page_size).limit(query.page_size))
        return PageResultSchema[SupplierOptionSchema](
            page_no=query.page_no,
            page_size=query.page_size,
            total=total,
            has_next=query.page_no * query.page_size < total,
            items=[SupplierOptionSchema.model_validate(row) for row in result.mappings()],
        )

    async def get_by_code(self, supplier_code: str) -> SupplierModel | None:
        """按供应商编码查询未删除供应商。"""
        return await self.get(supplier_code=supplier_code)

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema, PageResultSchema

from ..model import WarehouseModel
from ..option_schema import ArchiveOptionQuery
from .schema import WarehouseCreateSchema, WarehouseOptionSchema, WarehouseUpdateSchema


class WarehouseCRUD(CRUDBase[WarehouseModel, WarehouseCreateSchema, WarehouseUpdateSchema]):
    """仓库数据访问层，仓库档案不按创建人隔离。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=WarehouseModel, auth=auth, db=db, enforce_data_scope=False)

    async def options(self, query: ArchiveOptionQuery) -> PageResultSchema[WarehouseOptionSchema]:
        """仅查询下拉必要列，沿用软删除及共享档案范围，不加载用户关系。"""
        conditions = await self._build_conditions(status=query.status)
        if query.keyword:
            conditions.append(or_(WarehouseModel.warehouse_code.contains(query.keyword, autoescape=True), WarehouseModel.warehouse_name.contains(query.keyword, autoescape=True)))
        total = await self.db.scalar(select(func.count()).select_from(WarehouseModel).where(*conditions)) or 0
        statement = (
            select(WarehouseModel.id, WarehouseModel.warehouse_code, WarehouseModel.warehouse_name, WarehouseModel.status, WarehouseModel.is_default)
            .where(*conditions)
            .order_by(WarehouseModel.is_default.desc(), WarehouseModel.id.asc())
        )
        result = await self.db.execute(statement.offset((query.page_no - 1) * query.page_size).limit(query.page_size))
        return PageResultSchema[WarehouseOptionSchema](
            page_no=query.page_no,
            page_size=query.page_size,
            total=total,
            has_next=query.page_no * query.page_size < total,
            items=[WarehouseOptionSchema.model_validate(row) for row in result.mappings()],
        )

    async def get_by_code(self, warehouse_code: str) -> WarehouseModel | None:
        """按仓库编码查询仓库，包含已软删除数据以保护唯一约束。"""
        return await self.get(warehouse_code=warehouse_code, include_deleted=True)

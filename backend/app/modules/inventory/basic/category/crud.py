from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from ..model import GoodsCategoryModel, GoodsModel
from .schema import GoodsCategoryCreateSchema, GoodsCategoryUpdateSchema


class GoodsCategoryCRUD(CRUDBase[GoodsCategoryModel, GoodsCategoryCreateSchema, GoodsCategoryUpdateSchema]):
    """商品分类数据访问层，分类档案不按创建人隔离。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=GoodsCategoryModel, auth=auth, db=db, enforce_data_scope=False)

    async def get_same_level(
        self,
        *,
        name: str,
        parent_id: int | None,
        exclude_id: int | None = None,
    ) -> GoodsCategoryModel | None:
        """查询同一父级下的同名分类。"""
        statement = select(GoodsCategoryModel).where(
            GoodsCategoryModel.is_deleted.is_(False),
            GoodsCategoryModel.name == name,
        )
        if parent_id is None:
            statement = statement.where(GoodsCategoryModel.parent_id.is_(None))
        else:
            statement = statement.where(GoodsCategoryModel.parent_id == parent_id)
        if exclude_id is not None:
            statement = statement.where(GoodsCategoryModel.id != exclude_id)
        result = await self.db.execute(statement)
        return result.scalars().first()

    async def count_goods(self, category_ids: list[int]) -> int:
        """统计分类下尚未删除的商品数量。"""
        statement = select(func.count()).select_from(GoodsModel).where(
            GoodsModel.is_deleted.is_(False),
            GoodsModel.category_id.in_(category_ids),
        )
        result = await self.db.execute(statement)
        return result.scalar() or 0

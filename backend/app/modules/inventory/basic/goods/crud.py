from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from ..model import GoodsCategoryModel, GoodsModel
from .schema import GoodsCreateSchema, GoodsUpdateSchema


class GoodsCRUD(CRUDBase[GoodsModel, GoodsCreateSchema, GoodsUpdateSchema]):
    """商品数据访问层，商品档案不按创建人隔离。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=GoodsModel, auth=auth, db=db, enforce_data_scope=False)

    async def get_by_code(self, goods_code: str) -> GoodsModel | None:
        """按商品编码查询未删除商品。"""
        return await self.get(goods_code=goods_code)

    async def get_category_name_map(self, category_ids: set[int]) -> dict[int, str]:
        """批量查询商品分类名称，避免列表逐条查询。"""
        if not category_ids:
            return {}
        statement = select(GoodsCategoryModel.id, GoodsCategoryModel.name).where(
            GoodsCategoryModel.is_deleted.is_(False),
            GoodsCategoryModel.id.in_(category_ids),
        )
        result = await self.db.execute(statement)
        return dict(result.all())

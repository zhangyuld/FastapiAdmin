from typing import Any

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, BatchSetAvailable
from app.core.exceptions import CustomException
from app.utils.common_util import (
    get_child_id_map,
    get_child_recursion,
    get_parent_id_map,
    get_parent_recursion,
    search_to_dict,
    traversal_to_tree,
)

from .crud import GoodsCategoryCRUD
from .schema import (
    GoodsCategoryCreateSchema,
    GoodsCategoryOutSchema,
    GoodsCategoryQueryParam,
    GoodsCategoryUpdateSchema,
)


class GoodsCategoryService:
    """商品分类业务服务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db
        self.crud = GoodsCategoryCRUD(auth, db)

    async def detail(self, id: int) -> GoodsCategoryOutSchema:
        """查询分类详情并补充父分类名称。"""
        category = await self.crud.get(id=id)
        if category is None:
            raise CustomException(msg="商品分类不存在", status_code=status.HTTP_404_NOT_FOUND)
        category_out = GoodsCategoryOutSchema.model_validate(category)
        if category.parent_id:
            parent = await self.crud.get(id=category.parent_id)
            if parent:
                category_out.parent_name = parent.name
        return category_out

    async def tree(
        self,
        search: GoodsCategoryQueryParam | None = None,
    ) -> list[dict[str, Any]]:
        """按排序和主键顺序返回商品分类树。"""
        categories = await self.crud.get_list(
            search=search_to_dict(search),
            order_by=[{"sort": "asc"}, {"id": "asc"}],
        )
        category_dicts = [GoodsCategoryOutSchema.model_validate(item).model_dump() for item in categories]
        return traversal_to_tree(category_dicts)

    async def create(self, data: GoodsCategoryCreateSchema) -> GoodsCategoryOutSchema:
        """创建分类并维护父级启用状态。"""
        await self._validate_parent(parent_id=data.parent_id)
        await self._validate_unique_name(name=data.name, parent_id=data.parent_id)
        category = await self.crud.create(data=data)
        if data.status == 0:
            await self.set_available(BatchSetAvailable(ids=[category.id], status=0))
        return await self.detail(id=category.id)

    async def update(self, id: int, data: GoodsCategoryUpdateSchema) -> GoodsCategoryOutSchema:
        """修改分类并阻止形成循环层级。"""
        if await self.crud.get(id=id) is None:
            raise CustomException(msg="更新失败，该分类不存在", status_code=status.HTTP_404_NOT_FOUND)
        await self._validate_parent(parent_id=data.parent_id, current_id=id)
        await self._validate_unique_name(name=data.name, parent_id=data.parent_id, exclude_id=id)
        update_data = data.model_dump(exclude_unset=True, exclude={"status"})
        await self.crud.update(id=id, data=update_data)
        await self.set_available(BatchSetAvailable(ids=[id], status=data.status))
        return await self.detail(id=id)

    async def delete(self, ids: list[int]) -> None:
        """删除无子分类且未被商品使用的分类。"""
        if not ids:
            raise CustomException(msg="删除失败，删除对象不能为空", status_code=status.HTTP_400_BAD_REQUEST)
        categories = list(await self.crud.get_list())
        existing_ids = {item.id for item in categories}
        missing_ids = sorted(set(ids) - existing_ids)
        if missing_ids:
            raise CustomException(
                msg=f"删除失败，分类不存在：{', '.join(map(str, missing_ids))}",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        child_id_map = get_child_id_map(categories)
        if any(child_id_map.get(category_id) for category_id in ids):
            raise CustomException(msg="存在子分类，不允许删除父分类", status_code=status.HTTP_409_CONFLICT)
        if await self.crud.count_goods(ids):
            raise CustomException(msg="分类已被商品使用，不允许删除", status_code=status.HTTP_409_CONFLICT)
        await self.crud.delete(ids=ids)

    async def set_available(self, data: BatchSetAvailable) -> None:
        """停用时级联子分类，启用时级联父分类。"""
        if not data.ids:
            raise CustomException(msg="状态修改失败，操作对象不能为空", status_code=status.HTTP_400_BAD_REQUEST)
        categories = list(await self.crud.get_list())
        existing_ids = {item.id for item in categories}
        missing_ids = sorted(set(data.ids) - existing_ids)
        if missing_ids:
            raise CustomException(
                msg=f"状态修改失败，分类不存在：{', '.join(map(str, missing_ids))}",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        total_ids: set[int] = set()
        if data.status == 0:
            parent_id_map = get_parent_id_map(categories)
            for category_id in data.ids:
                total_ids.update(get_parent_recursion(id=category_id, id_map=parent_id_map))
        else:
            child_id_map = get_child_id_map(categories)
            for category_id in data.ids:
                total_ids.update(get_child_recursion(id=category_id, id_map=child_id_map))
        await self.crud.set(ids=sorted(total_ids), status=data.status)

    async def _validate_parent(self, parent_id: int | None, current_id: int | None = None) -> None:
        """校验父分类存在且不属于当前分类子树。"""
        if parent_id is None:
            return
        if await self.crud.get(id=parent_id) is None:
            raise CustomException(msg="上级分类不存在", status_code=status.HTTP_404_NOT_FOUND)
        if current_id is None:
            return
        categories = list(await self.crud.get_list())
        descendants = set(get_child_recursion(id=current_id, id_map=get_child_id_map(categories)))
        if parent_id in descendants:
            raise CustomException(
                msg="上级分类不能选择当前分类或其子分类",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    async def _validate_unique_name(
        self,
        *,
        name: str,
        parent_id: int | None,
        exclude_id: int | None = None,
    ) -> None:
        """校验同一父级下分类名称唯一。"""
        duplicate = await self.crud.get_same_level(name=name, parent_id=parent_id, exclude_id=exclude_id)
        if duplicate:
            raise CustomException(
                msg="同一上级分类下已存在同名分类",
                status_code=status.HTTP_409_CONFLICT,
            )

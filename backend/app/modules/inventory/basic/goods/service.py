from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.utils.common_util import search_to_dict
from app.utils.excel_util import ExcelUtil

from ..category.crud import GoodsCategoryCRUD
from .crud import GoodsCRUD
from .schema import GoodsCreateSchema, GoodsDeleteSchema, GoodsExportSchema, GoodsOutSchema, GoodsQueryParam

GOODS_EXPORT_COLUMNS: dict[str, str] = {
    "goods_code": "商品编码",
    "goods_name": "商品名称",
    "category_name": "商品分类",
    "spec": "规格型号",
    "unit": "单位",
    "reference_cost_price": "参考进价",
    "sale_price": "默认销售价",
    "stock_min": "最低库存",
    "stock_max": "最高库存",
    "status": "状态",
    "remark": "备注",
    "created_time": "创建时间",
    "updated_time": "更新时间",
}


class GoodsService:
    """商品业务服务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db
        self.crud = GoodsCRUD(auth, db)
        self.category_crud = GoodsCategoryCRUD(auth, db)

    async def detail(self, id: int) -> GoodsOutSchema:
        """查询商品详情并补充分类名称。"""
        goods = await self.crud.get(id=id)
        if goods is None:
            raise CustomException(msg="商品不存在", status_code=status.HTTP_404_NOT_FOUND)
        result = GoodsOutSchema.model_validate(goods)
        category = await self.category_crud.get(id=goods.category_id)
        if category:
            result.category_name = category.name
        return result

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: GoodsQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[GoodsOutSchema]:
        """分页查询商品并补充分类名称。"""
        offset = (page_no - 1) * page_size
        result = await self.crud.page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "desc"}],
            search=search_to_dict(search),
            out_schema=GoodsOutSchema,
        )
        await self._fill_category_names(result.items)
        return result

    async def create(self, data: GoodsCreateSchema) -> GoodsOutSchema:
        """校验分类和编码后创建商品。"""
        category = await self.category_crud.get(id=data.category_id)
        if category is None:
            raise CustomException(msg="商品分类不存在", status_code=status.HTTP_404_NOT_FOUND)
        if category.status == 1:
            raise CustomException(msg="商品分类已停用", status_code=status.HTTP_400_BAD_REQUEST)
        if await self.crud.get_by_code(data.goods_code):
            raise CustomException(msg="商品编码已存在", status_code=status.HTTP_409_CONFLICT)

        goods = await self.crud.create(data=data)
        result = GoodsOutSchema.model_validate(goods)
        result.category_name = category.name
        return result

    async def update(self, id: int, data: GoodsCreateSchema) -> GoodsOutSchema:
        """校验分类和编码后更新商品。"""
        goods = await self.crud.get(id=id)
        if goods is None:
            raise CustomException(msg="商品不存在", status_code=status.HTTP_404_NOT_FOUND)

        category = await self.category_crud.get(id=data.category_id)
        if category is None:
            raise CustomException(msg="商品分类不存在", status_code=status.HTTP_404_NOT_FOUND)
        if category.status == 1:
            raise CustomException(msg="商品分类已停用", status_code=status.HTTP_400_BAD_REQUEST)

        if goods.goods_code != data.goods_code and await self.crud.get_by_code(data.goods_code):
            raise CustomException(msg="商品编码已存在", status_code=status.HTTP_409_CONFLICT)

        update_data = data.model_dump(exclude_unset=True)
        await self.crud.update(id=id, data=update_data)
        result = GoodsOutSchema.model_validate(goods)
        result.category_name = category.name
        return result

    async def delete(self, data: GoodsDeleteSchema) -> list[int]:
        """校验商品存在后批量软删除。"""
        ids = data.ids
        existing_goods = await self.crud.get_list(search={"id": ("in", ids)})
        existing_ids = {item.id for item in existing_goods}
        missing_ids = sorted(set(ids) - existing_ids)
        if missing_ids:
            raise CustomException(
                msg=f"删除失败，商品不存在：{', '.join(map(str, missing_ids))}",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self.crud.delete(ids=ids)
        return [item_id for item_id in ids if item_id in existing_ids]

    async def export(self, data: GoodsExportSchema) -> bytes:
        """按查询条件、字段和格式生成商品导出文件。"""
        goods_models = await self.crud.get_list(
            search=search_to_dict(data.query),
            order_by=[{"id": "asc"}],
        )
        goods_list = [GoodsOutSchema.model_validate(item) for item in goods_models]
        await self._fill_category_names(goods_list)
        rows = [item.model_dump() for item in goods_list]
        for item in rows:
            item["status"] = "启用" if item.get("status") == 0 else "停用"
        mapping_dict = {field: GOODS_EXPORT_COLUMNS[field] for field in data.fields}
        if data.format == "csv":
            return await ExcelUtil.aexport_list2csv(list_data=rows, mapping_dict=mapping_dict)
        return await ExcelUtil.aexport_list2excel(list_data=rows, mapping_dict=mapping_dict, sheet_name=data.sheet_name)

    async def _fill_category_names(self, items: list[GoodsOutSchema]) -> None:
        """批量补充商品响应中的分类名称。"""
        category_map = await self.crud.get_category_name_map({item.category_id for item in items})
        for item in items:
            item.category_name = category_map.get(item.category_id)

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.utils.common_util import search_to_dict
from app.utils.excel_util import ExcelUtil

from ..option_schema import ArchiveOptionQuery
from .crud import WarehouseCRUD
from .schema import (
    WarehouseCreateSchema,
    WarehouseDeleteSchema,
    WarehouseExportSchema,
    WarehouseOptionSchema,
    WarehouseOutSchema,
    WarehouseQueryParam,
    WarehouseStatusSchema,
    WarehouseUpdateSchema,
)

WAREHOUSE_EXPORT_COLUMNS: dict[str, str] = {
    "warehouse_code": "仓库编码",
    "warehouse_name": "仓库名称",
    "address": "地址",
    "status": "状态",
    "remark": "备注",
    "created_time": "创建时间",
    "updated_time": "更新时间",
}


class WarehouseService:
    """仓库业务服务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db
        self.crud = WarehouseCRUD(auth, db)

    async def options(self, query: ArchiveOptionQuery) -> PageResultSchema[WarehouseOptionSchema]:
        """供已登录业务页面读取精简档案，不复用管理列表响应。"""
        return await self.crud.options(query)

    async def detail(self, id: int) -> WarehouseOutSchema:
        """查询仓库详情。"""
        warehouse = await self.crud.get(id=id)
        if warehouse is None:
            raise CustomException(msg="仓库不存在", status_code=status.HTTP_404_NOT_FOUND)
        result = WarehouseOutSchema.model_validate(warehouse)
        return result

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: WarehouseQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[WarehouseOutSchema]:
        """分页查询仓库。"""
        offset = (page_no - 1) * page_size
        result = await self.crud.page(
            offset=offset,
            limit=page_size,
            search=search_to_dict(search),
            order_by=order_by or [{"id": "desc"}],
            out_schema=WarehouseOutSchema,
        )
        return result

    async def create(self, data: WarehouseCreateSchema) -> WarehouseOutSchema:
        """创建仓库。"""
        if await self.crud.get_by_code(data.warehouse_code):
            raise CustomException(msg="仓库编码已存在", status_code=status.HTTP_409_CONFLICT)
        warehouse = await self.crud.create(data=data)
        result = WarehouseOutSchema.model_validate(warehouse)
        return result

    async def update(self, id: int, data: WarehouseUpdateSchema) -> WarehouseOutSchema:
        """修改仓库。"""
        warehouse = await self.crud.get(id=id)
        if warehouse is None:
            raise CustomException(msg="仓库不存在", status_code=status.HTTP_404_NOT_FOUND)
        if data.warehouse_code != warehouse.warehouse_code and await self.crud.get_by_code(data.warehouse_code):
            raise CustomException(msg="仓库编码已存在", status_code=status.HTTP_409_CONFLICT)
        update_data = data.model_dump(exclude_unset=True)
        warehouse = await self.crud.update(id=id, data=update_data)
        result = WarehouseOutSchema.model_validate(warehouse)
        return result

    async def delete(self, data: WarehouseDeleteSchema) -> list[int]:
        """删除仓库。"""
        ids = data.ids
        existing_ids = await self._validate_existing_ids(ids, "删除")
        await self.crud.delete(ids=ids)
        return [item_id for item_id in ids if item_id in existing_ids]

    async def set_status(self, data: WarehouseStatusSchema) -> None:
        """批量修改仓库状态。"""
        await self._validate_existing_ids(data.ids, "状态修改")
        await self.crud.set(ids=data.ids, status=data.status)

    async def export(self, data: WarehouseExportSchema) -> bytes:
        """导出仓库列表为Excel或CSV文件。"""
        warehouse_models = await self.crud.get_list(
            search=search_to_dict(data.query),
            order_by=[{"id": "asc"}],
        )
        warehouse_list = [WarehouseOutSchema.model_validate(item) for item in warehouse_models]
        rows = [item.model_dump() for item in warehouse_list]
        for item in rows:
            item["status"] = "启用" if item.get("status") == 0 else "停用"
        mapping_dict = {field: WAREHOUSE_EXPORT_COLUMNS[field] for field in data.fields}
        if data.format == "csv":
            return await ExcelUtil.aexport_list2csv(list_data=rows, mapping_dict=mapping_dict)
        return await ExcelUtil.aexport_list2excel(list_data=rows, mapping_dict=mapping_dict, sheet_name=data.sheet_name)

    async def _validate_existing_ids(self, ids: list[int], operation: str) -> set[int]:
        """校验批量操作涉及的仓库均存在。"""
        existing_warehouses = await self.crud.get_list(search={"id": ("in", ids)})
        existing_ids = {item.id for item in existing_warehouses}
        missing_ids = sorted(set(ids) - existing_ids)
        if missing_ids:
            raise CustomException(
                msg=f"{operation}失败，仓库不存在：{', '.join(map(str, missing_ids))}",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return existing_ids

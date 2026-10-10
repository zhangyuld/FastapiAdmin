from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.utils.common_util import search_to_dict
from app.utils.excel_util import ExcelUtil

from .crud import SupplierCRUD
from .schema import SupplierCreateSchema, SupplierUpdateSchema, SupplierDeleteSchema, SupplierExportSchema, SupplierOutSchema, SupplierQueryParam, SupplierStatusSchema

SUPPLIER_EXPORT_COLUMNS: dict[str, str] = {
    "supplier_code": "供应商编码",
    "supplier_name": "供应商名称",
    "contact": "联系人",
    "phone": "联系电话",
    "address": "地址",
    "status": "状态",
    "remark": "备注",
    "created_time": "创建时间",
    "updated_time": "更新时间",
}


class SupplierService:
    """供应商业务服务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db
        self.crud = SupplierCRUD(auth, db)

    async def detail(self, id: int) -> SupplierOutSchema:
        """查询供应商详情。"""
        supplier = await self.crud.get(id=id)
        if supplier is None:
            raise CustomException(msg="供应商不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SupplierOutSchema.model_validate(supplier)

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: SupplierQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[SupplierOutSchema]:
        """分页查询供应商。"""
        offset = (page_no - 1) * page_size
        result = await self.crud.page(
            offset=offset,
            limit=page_size,
            search=search_to_dict(search),
            order_by=order_by or [{"id": "desc"}],
            out_schema=SupplierOutSchema,
        )
        return result

    async def create(self, data: SupplierCreateSchema) -> SupplierOutSchema:
        """创建供应商。"""
        if await self.crud.get_by_code(data.supplier_code):
            raise CustomException(msg="供应商编码已存在", status_code=status.HTTP_409_CONFLICT)
        supplier = await self.crud.create(data=data)
        result = SupplierOutSchema.model_validate(supplier)
        return result

    async def update(self, id: int, data: SupplierUpdateSchema) -> SupplierOutSchema:
        """修改供应商。"""
        supplier = await self.crud.get(id=id)
        if supplier is None:
            raise CustomException(msg="供应商不存在", status_code=status.HTTP_404_NOT_FOUND)
        if data.supplier_code != supplier.supplier_code and await self.crud.get_by_code(data.supplier_code):
            raise CustomException(msg="供应商编码已存在", status_code=status.HTTP_409_CONFLICT)
        update_data = data.model_dump(exclude_unset=True)
        supplier = await self.crud.update(id=id, data=update_data)
        result = SupplierOutSchema.model_validate(supplier)
        return result

    async def delete(self, data: SupplierDeleteSchema) -> list[int]:
        """删除供应商。"""
        ids = data.ids
        existing_ids = await self._validate_existing_ids(ids, "删除")
        await self.crud.delete(ids=ids)
        return [item_id for item_id in ids if item_id in existing_ids]

    async def set_status(self, data: SupplierStatusSchema) -> None:
        """批量修改供应商状态。"""
        await self._validate_existing_ids(data.ids, "状态修改")
        await self.crud.set(ids=data.ids, status=data.status)

    async def export(self, data: SupplierExportSchema) -> bytes:
        """导出供应商列表为Excel或CSV文件。"""
        supplier_models = await self.crud.get_list(
            search=search_to_dict(data.query),
            order_by=[{"id": "asc"}],
        )
        supplier_list = [SupplierOutSchema.model_validate(item) for item in supplier_models]
        rows = [item.model_dump() for item in supplier_list]
        for item in rows:
            item["status"] = "启用" if item.get("status") == 0 else "停用"
        mapping_dict = {field: SUPPLIER_EXPORT_COLUMNS[field] for field in data.fields}
        if data.format == "csv":
            return await ExcelUtil.aexport_list2csv(list_data=rows, mapping_dict=mapping_dict)
        return await ExcelUtil.aexport_list2excel(list_data=rows, mapping_dict=mapping_dict, sheet_name=data.sheet_name)

    async def _validate_existing_ids(self, ids: list[int], operation: str) -> set[int]:
        """校验批量操作涉及的供应商均存在。"""
        existing_suppliers = await self.crud.get_list(search={"id": ("in", ids)})
        existing_ids = {item.id for item in existing_suppliers}
        missing_ids = sorted(set(ids) - existing_ids)
        if missing_ids:
            raise CustomException(
                msg=f"{operation}失败，供应商不存在：{', '.join(map(str, missing_ids))}",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return existing_ids


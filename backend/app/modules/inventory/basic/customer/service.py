from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.utils.common_util import search_to_dict
from app.utils.excel_util import ExcelUtil

from .crud import CustomerCRUD
from .schema import (
    CustomerCreateSchema,
    CustomerDeleteSchema,
    CustomerExportSchema,
    CustomerOutSchema,
    CustomerQueryParam,
    CustomerStatusSchema,
    CustomerUpdateSchema,
)

CUSTOMER_EXPORT_COLUMNS: dict[str, str] = {
    "customer_code": "客户编码",
    "customer_name": "客户名称",
    "contact": "联系人",
    "phone": "联系电话",
    "address": "地址",
    "status": "状态",
    "remark": "备注",
    "created_time": "创建时间",
    "updated_time": "更新时间",
}


class CustomerService:
    """客户业务服务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db
        self.crud = CustomerCRUD(auth, db)

    async def detail(self, id: int) -> CustomerOutSchema:
        """查询客户详情。"""
        customer = await self.crud.get(id=id)
        if customer is None:
            raise CustomException(msg="客户不存在", status_code=status.HTTP_404_NOT_FOUND)
        result = CustomerOutSchema.model_validate(customer)
        return result

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: CustomerQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[CustomerOutSchema]:
        """分页查询客户。"""
        offset = (page_no - 1) * page_size
        result = await self.crud.page(
            offset=offset,
            limit=page_size,
            search=search_to_dict(search),
            order_by=order_by or [{"id": "desc"}],
            out_schema=CustomerOutSchema,
        )
        return result

    async def create(self, data: CustomerCreateSchema) -> CustomerOutSchema:
        """创建客户。"""
        if await self.crud.get_by_code(data.customer_code):
            raise CustomException(msg="客户编码已存在", status_code=status.HTTP_409_CONFLICT)
        customer = await self.crud.create(data=data)
        result = CustomerOutSchema.model_validate(customer)
        return result

    async def update(self, id: int, data: CustomerUpdateSchema) -> CustomerOutSchema:
        """修改客户。"""
        customer = await self.crud.get(id=id)
        if customer is None:
            raise CustomException(msg="客户不存在", status_code=status.HTTP_404_NOT_FOUND)
        if data.customer_code != customer.customer_code and await self.crud.get_by_code(data.customer_code):
            raise CustomException(msg="客户编码已存在", status_code=status.HTTP_409_CONFLICT)
        update_data = data.model_dump(exclude_unset=True)
        customer = await self.crud.update(id=id, data=update_data)
        result = CustomerOutSchema.model_validate(customer)
        return result

    async def delete(self, data: CustomerDeleteSchema) -> list[int]:
        """删除客户。"""
        ids = data.ids
        existing_ids = await self._validate_existing_ids(ids, "删除")
        await self.crud.delete(ids=ids)
        return [item_id for item_id in ids if item_id in existing_ids]

    async def set_status(self, data: CustomerStatusSchema) -> None:
        """批量修改客户状态。"""
        await self._validate_existing_ids(data.ids, "状态修改")
        await self.crud.set(ids=data.ids, status=data.status)

    async def export(self, data: CustomerExportSchema) -> bytes:
        """导出客户列表为Excel或CSV文件。"""
        customer_models = await self.crud.get_list(
            search=search_to_dict(data.query),
            order_by=[{"id": "asc"}],
        )
        customer_list = [CustomerOutSchema.model_validate(item) for item in customer_models]
        rows = [item.model_dump() for item in customer_list]
        for item in rows:
            item["status"] = "启用" if item.get("status") == 0 else "停用"
        mapping_dict = {field: CUSTOMER_EXPORT_COLUMNS[field] for field in data.fields}
        if data.format == "csv":
            return await ExcelUtil.aexport_list2csv(list_data=rows, mapping_dict=mapping_dict)
        return await ExcelUtil.aexport_list2excel(list_data=rows, mapping_dict=mapping_dict, sheet_name=data.sheet_name)

    async def _validate_existing_ids(self, ids: list[int], operation: str) -> set[int]:
        """校验批量操作涉及的客户均存在。"""
        existing_customers = await self.crud.get_list(search={"id": ("in", ids)})
        existing_ids = {item.id for item in existing_customers}
        missing_ids = sorted(set(ids) - existing_ids)
        if missing_ids:
            raise CustomException(
                msg=f"{operation}失败，客户不存在：{', '.join(map(str, missing_ids))}",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return existing_ids

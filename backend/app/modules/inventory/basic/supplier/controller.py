from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, Path, Query, Security, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, StreamResponse, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute
from app.utils.common_util import bytes2file_response

from .schema import SupplierCreateSchema, SupplierUpdateSchema, SupplierDeleteSchema, SupplierExportSchema, SupplierOutSchema, SupplierQueryParam, SupplierStatusSchema
from .service import SupplierService

SupplierRouter = APIRouter(route_class=OperationLogRoute, prefix="/supplier", tags=["供应商管理"])


@SupplierRouter.get("/detail/{id}", summary="查询供应商详情", response_model=ResponseSchema[SupplierOutSchema])
async def get_supplier_detail_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:supplier:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="供应商ID", ge=1)],
) -> JSONResponse:
    result = await SupplierService(auth, db).detail(id=id)
    return SuccessResponse(data=result, msg="查询供应商详情成功")


@SupplierRouter.get("/list", summary="分页查询供应商列表", response_model=ResponseSchema[PageResultSchema[SupplierOutSchema]])
async def get_supplier_list_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:supplier:query"]))],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[SupplierQueryParam, Query()],
    db: Annotated[AsyncSession, Depends(db_getter)],
) -> JSONResponse:
    result: PageResultSchema[SupplierOutSchema] = await SupplierService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="分页查询供应商列表成功")


@SupplierRouter.post("/create", status_code=status.HTTP_201_CREATED, summary="创建供应商", response_model=ResponseSchema[SupplierOutSchema])
async def create_supplier_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:supplier:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[SupplierCreateSchema, Body(description="供应商创建参数")],
) -> JSONResponse:
    result = await SupplierService(auth, db).create(data=data)
    return SuccessResponse(data=result, msg="创建供应商成功")


@SupplierRouter.post("/update/{id}", summary="修改供应商", response_model=ResponseSchema[SupplierOutSchema])
async def update_supplier_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:supplier:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="供应商ID", ge=1)],
    data: Annotated[SupplierUpdateSchema, Body(description="供应商更新参数")],
) -> JSONResponse:
    result = await SupplierService(auth, db).update(id=id, data=data)
    return SuccessResponse(data=result, msg="修改供应商成功")


@SupplierRouter.post("/delete", summary="删除供应商", response_model=ResponseSchema[list[int]])
async def delete_supplier_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:supplier:delete"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[SupplierDeleteSchema, Body(description="供应商删除参数")],
) -> JSONResponse:
    result = await SupplierService(auth, db).delete(data=data)
    return SuccessResponse(data=result, msg="删除供应商成功")


@SupplierRouter.post("/status/batch", summary="批量修改供应商状态", response_model=ResponseSchema[None])
async def batch_supplier_status_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:supplier:patch"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[SupplierStatusSchema, Body(description="供应商状态设置")],
) -> JSONResponse:
    await SupplierService(auth, db).set_status(data=data)
    return SuccessResponse(msg="修改供应商状态成功")


@SupplierRouter.post("/export", summary="导出供应商")
async def export_supplier_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:supplier:export"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[SupplierExportSchema, Body()],
) -> StreamingResponse:
    result = await SupplierService(auth, db).export(data=data)
    media_type = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    filename = data.get_download_filename()
    return StreamResponse(
        data=bytes2file_response(result),
        media_type=media_type,
        headers={"Content-Disposition": (f"attachment; filename=supplier.{data.format}; filename*=UTF-8''{quote(filename)}")},
    )

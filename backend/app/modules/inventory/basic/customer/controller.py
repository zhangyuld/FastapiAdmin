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

from ..option_schema import ArchiveOptionQuery
from .schema import (
    CustomerCreateSchema,
    CustomerDeleteSchema,
    CustomerExportSchema,
    CustomerOptionSchema,
    CustomerOutSchema,
    CustomerQueryParam,
    CustomerStatusSchema,
    CustomerUpdateSchema,
)
from .service import CustomerService

CustomerRouter = APIRouter(route_class=OperationLogRoute, prefix="/customer", tags=["客户管理"])


@CustomerRouter.get("/options", summary="查询客户轻量选项", response_model=ResponseSchema[PageResultSchema[CustomerOptionSchema]])
async def get_customer_options_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission())],
    db: Annotated[AsyncSession, Depends(db_getter)],
    query: Annotated[ArchiveOptionQuery, Query()],
) -> JSONResponse:
    """只校验有效登录和系统级访问规则，不要求基础档案查询权限。"""
    result = await CustomerService(auth, db).options(query)
    return SuccessResponse(data=result)


@CustomerRouter.get("/detail/{id}", summary="查询客户详情", response_model=ResponseSchema[CustomerOutSchema])
async def get_customer_detail_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:customer:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="客户ID", ge=1)],
) -> JSONResponse:
    result = await CustomerService(auth, db).detail(id=id)
    return SuccessResponse(data=result, msg="查询客户详情成功")


@CustomerRouter.get("/list", summary="分页查询客户列表", response_model=ResponseSchema[PageResultSchema[CustomerOutSchema]])
async def get_customer_list_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:customer:query"]))],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[CustomerQueryParam, Query()],
    db: Annotated[AsyncSession, Depends(db_getter)],
) -> JSONResponse:
    result: PageResultSchema[CustomerOutSchema] = await CustomerService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="分页查询客户列表成功")


@CustomerRouter.post("/create", status_code=status.HTTP_201_CREATED, summary="创建客户", response_model=ResponseSchema[CustomerOutSchema])
async def create_customer_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:customer:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[CustomerCreateSchema, Body(description="客户创建参数")],
) -> JSONResponse:
    result = await CustomerService(auth, db).create(data=data)
    return SuccessResponse(data=result, msg="创建客户成功")


@CustomerRouter.post("/update/{id}", summary="修改客户", response_model=ResponseSchema[CustomerOutSchema])
async def update_customer_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:customer:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="客户ID", ge=1)],
    data: Annotated[CustomerUpdateSchema, Body(description="客户更新参数")],
) -> JSONResponse:
    result = await CustomerService(auth, db).update(id=id, data=data)
    return SuccessResponse(data=result, msg="修改客户成功")


@CustomerRouter.post("/delete", summary="删除客户", response_model=ResponseSchema[list[int]])
async def delete_customer_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:customer:delete"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[CustomerDeleteSchema, Body(description="客户删除参数")],
) -> JSONResponse:
    result = await CustomerService(auth, db).delete(data=data)
    return SuccessResponse(data=result, msg="删除客户成功")


@CustomerRouter.post("/status/batch", summary="批量修改客户状态", response_model=ResponseSchema[None])
async def batch_customer_status_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:customer:patch"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[CustomerStatusSchema, Body(description="客户状态设置")],
) -> JSONResponse:
    await CustomerService(auth, db).set_status(data=data)
    return SuccessResponse(msg="修改客户状态成功")


@CustomerRouter.post("/export", summary="导出客户")
async def export_customer_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:customer:export"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[CustomerExportSchema, Body()],
) -> StreamingResponse:
    result = await CustomerService(auth, db).export(data=data)
    media_type = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    filename = data.get_download_filename()
    return StreamResponse(
        data=bytes2file_response(result),
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename=customer.{data.format}; "
                f"filename*=UTF-8''{quote(filename)}"
            )
        },
    )

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
    WarehouseCreateSchema,
    WarehouseDeleteSchema,
    WarehouseExportSchema,
    WarehouseOptionSchema,
    WarehouseOutSchema,
    WarehouseQueryParam,
    WarehouseStatusSchema,
    WarehouseUpdateSchema,
)
from .service import WarehouseService

WarehouseRouter = APIRouter(route_class=OperationLogRoute, prefix="/warehouse", tags=["仓库管理"])


@WarehouseRouter.get("/options", summary="查询仓库轻量选项", response_model=ResponseSchema[PageResultSchema[WarehouseOptionSchema]])
async def get_warehouse_options_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission())],
    db: Annotated[AsyncSession, Depends(db_getter)],
    query: Annotated[ArchiveOptionQuery, Query()],
) -> JSONResponse:
    """只校验有效登录和系统级访问规则，不要求基础档案查询权限。"""
    result = await WarehouseService(auth, db).options(query)
    return SuccessResponse(data=result)


@WarehouseRouter.get("/detail/{id}", summary="查询仓库详情", response_model=ResponseSchema[WarehouseOutSchema])
async def get_warehouse_detail_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:warehouse:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="仓库ID", ge=1)],
) -> JSONResponse:
    result = await WarehouseService(auth, db).detail(id=id)
    return SuccessResponse(data=result, msg="查询仓库详情成功")


@WarehouseRouter.get("/list", summary="分页查询仓库列表", response_model=ResponseSchema[PageResultSchema[WarehouseOutSchema]])
async def get_warehouse_list_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:warehouse:query"]))],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[WarehouseQueryParam, Query()],
    db: Annotated[AsyncSession, Depends(db_getter)],
) -> JSONResponse:
    result: PageResultSchema[WarehouseOutSchema] = await WarehouseService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="分页查询仓库列表成功")


@WarehouseRouter.post("/create", status_code=status.HTTP_201_CREATED, summary="创建仓库", response_model=ResponseSchema[WarehouseOutSchema])
async def create_warehouse_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:warehouse:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[WarehouseCreateSchema, Body(description="仓库创建参数")],
) -> JSONResponse:
    result = await WarehouseService(auth, db).create(data=data)
    return SuccessResponse(data=result, msg="创建仓库成功")


@WarehouseRouter.post("/update/{id}", summary="修改仓库", response_model=ResponseSchema[WarehouseOutSchema])
async def update_warehouse_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:warehouse:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="仓库ID", ge=1)],
    data: Annotated[WarehouseUpdateSchema, Body(description="仓库更新参数")],
) -> JSONResponse:
    result = await WarehouseService(auth, db).update(id=id, data=data)
    return SuccessResponse(data=result, msg="修改仓库成功")


@WarehouseRouter.post("/delete", summary="删除仓库", response_model=ResponseSchema[list[int]])
async def delete_warehouse_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:warehouse:delete"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[WarehouseDeleteSchema, Body(description="仓库删除参数")],
) -> JSONResponse:
    result = await WarehouseService(auth, db).delete(data=data)
    return SuccessResponse(data=result, msg="删除仓库成功")


@WarehouseRouter.post("/status/batch", summary="批量修改仓库状态", response_model=ResponseSchema[None])
async def batch_warehouse_status_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:warehouse:patch"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[WarehouseStatusSchema, Body(description="仓库状态设置")],
) -> JSONResponse:
    await WarehouseService(auth, db).set_status(data=data)
    return SuccessResponse(msg="修改仓库状态成功")


@WarehouseRouter.post("/export", summary="导出仓库")
async def export_warehouse_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:warehouse:export"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[WarehouseExportSchema, Body()],
) -> StreamingResponse:
    result = await WarehouseService(auth, db).export(data=data)
    media_type = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    filename = data.get_download_filename()
    return StreamResponse(
        data=bytes2file_response(result),
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename=warehouse.{data.format}; "
                f"filename*=UTF-8''{quote(filename)}"
            )
        },
    )

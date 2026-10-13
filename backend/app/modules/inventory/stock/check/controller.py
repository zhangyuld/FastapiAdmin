from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, StreamResponse, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute
from app.utils.common_util import bytes2file_response

from .schema import CheckCreateSchema, CheckUpdateSchema, DeleteBody, DocumentExport, DocumentQuery, StockDocumentOut, VersionBody, VoidBody
from .service import StockCheckService

StockCheckRouter = APIRouter(route_class=OperationLogRoute, prefix="/check", tags=["库存盘点"])


@StockCheckRouter.get("/list", response_model=ResponseSchema[PageResultSchema[StockDocumentOut]])
async def list_stock_check(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_check:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[DocumentQuery, Query()],
) -> JSONResponse:
    """分页查询库存盘点，排序和筛选在服务层验证。"""
    result = await StockCheckService(auth, db).page(page.page_no, page.page_size, search, page.order_by)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockCheckRouter.get("/detail/{id}", response_model=ResponseSchema[StockDocumentOut])
async def detail_stock_check(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_check:detail"]))], db: Annotated[AsyncSession, Depends(db_getter)], id: Annotated[int, Path(gt=0)]
) -> JSONResponse:
    """读取库存盘点详情并验证功能权限。"""
    result = await StockCheckService(auth, db).detail(id)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockCheckRouter.post("/create", response_model=ResponseSchema[StockDocumentOut])
async def create_stock_check(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_check:create"]))], db: Annotated[AsyncSession, Depends(db_getter)], data: Annotated[CheckCreateSchema, Body()]
) -> JSONResponse:
    """创建草稿，不产生库存变动。"""
    result = await StockCheckService(auth, db).create(data)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockCheckRouter.post("/update/{id}", response_model=ResponseSchema[StockDocumentOut])
async def update_stock_check(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_check:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0)],
    data: Annotated[CheckUpdateSchema, Body()],
) -> JSONResponse:
    """按版本更新草稿。"""
    result = await StockCheckService(auth, db).update(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockCheckRouter.post("/confirm/{id}", response_model=ResponseSchema[StockDocumentOut])
async def confirm_stock_check(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_check:confirm"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0)],
    data: Annotated[VersionBody, Body()],
) -> JSONResponse:
    """原子确认库存业务。"""
    result = await StockCheckService(auth, db).confirm(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockCheckRouter.post("/void/{id}", response_model=ResponseSchema[StockDocumentOut])
async def void_stock_check(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_check:void"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0)],
    data: Annotated[VoidBody, Body()],
) -> JSONResponse:
    """按原流水冲销已确认业务。"""
    result = await StockCheckService(auth, db).void(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockCheckRouter.post("/delete", response_model=ResponseSchema[list[int]])
async def delete_stock_check(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_check:delete"]))], db: Annotated[AsyncSession, Depends(db_getter)], data: Annotated[DeleteBody, Body()]
) -> JSONResponse:
    """按版本批量软删除草稿。"""
    result = await StockCheckService(auth, db).delete(data)
    return SuccessResponse(data=result)


@StockCheckRouter.post("/refresh/{id}", response_model=ResponseSchema[StockDocumentOut])
async def refresh_stock_check(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_check:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0)],
    data: Annotated[VersionBody, Body()],
) -> JSONResponse:
    """显式刷新草稿账面快照，实盘数量需用户重新核对。"""
    result = await StockCheckService(auth, db).refresh(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockCheckRouter.get("/snapshot")
async def get_stock_check_snapshot(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_check:create", "module_inventory:stock_check:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    warehouse_id: Annotated[int, Query(gt=0)],
    goods_ids: Annotated[list[Annotated[int, Field(gt=0)]], Query(min_length=1, max_length=500)],
) -> JSONResponse:
    """录入盘点时查询商品当前账面快照，快照不能由客户端提交。"""
    result = await StockCheckService(auth, db).snapshot(warehouse_id, list(dict.fromkeys(goods_ids)))
    return SuccessResponse(data=result)


@StockCheckRouter.post("/export")
async def export_stock_check(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_check:export"]))], db: Annotated[AsyncSession, Depends(db_getter)], data: Annotated[DocumentExport, Body()]
) -> StreamingResponse:
    """按选定字段生成库存盘点文件流并返回 UTF-8 下载名。"""
    content = await StockCheckService(auth, db).export(data)
    media = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamResponse(
        data=bytes2file_response(content),
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename=stock_check.{data.format}; filename*=UTF-8''{quote(data.download_name('库存盘点'))}"},
    )

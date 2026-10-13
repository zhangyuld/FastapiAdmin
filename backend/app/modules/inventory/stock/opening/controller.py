from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, StreamResponse, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute
from app.utils.common_util import bytes2file_response

from .schema import DeleteBody, DocumentExport, DocumentQuery, OpeningCreateSchema, OpeningUpdateSchema, StockDocumentOut, VersionBody, VoidBody
from .service import StockOpeningService

StockOpeningRouter = APIRouter(route_class=OperationLogRoute, prefix="/opening", tags=["期初库存"])


@StockOpeningRouter.get("/list", response_model=ResponseSchema[PageResultSchema[StockDocumentOut]])
async def list_stock_opening(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_opening:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[DocumentQuery, Query()],
) -> JSONResponse:
    """分页查询期初库存，排序和筛选在服务层验证。"""
    result = await StockOpeningService(auth, db).page(page.page_no, page.page_size, search, page.order_by)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockOpeningRouter.get("/detail/{id}", response_model=ResponseSchema[StockDocumentOut])
async def detail_stock_opening(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_opening:detail"]))], db: Annotated[AsyncSession, Depends(db_getter)], id: Annotated[int, Path(gt=0)]
) -> JSONResponse:
    """读取期初库存详情并验证功能权限。"""
    result = await StockOpeningService(auth, db).detail(id)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockOpeningRouter.post("/create", response_model=ResponseSchema[StockDocumentOut])
async def create_stock_opening(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_opening:create"]))], db: Annotated[AsyncSession, Depends(db_getter)], data: Annotated[OpeningCreateSchema, Body()]
) -> JSONResponse:
    """创建草稿，不产生库存变动。"""
    result = await StockOpeningService(auth, db).create(data)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockOpeningRouter.post("/update/{id}", response_model=ResponseSchema[StockDocumentOut])
async def update_stock_opening(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_opening:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0)],
    data: Annotated[OpeningUpdateSchema, Body()],
) -> JSONResponse:
    """按版本更新草稿。"""
    result = await StockOpeningService(auth, db).update(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockOpeningRouter.post("/confirm/{id}", response_model=ResponseSchema[StockDocumentOut])
async def confirm_stock_opening(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_opening:confirm"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0)],
    data: Annotated[VersionBody, Body()],
) -> JSONResponse:
    """原子确认库存业务。"""
    result = await StockOpeningService(auth, db).confirm(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockOpeningRouter.post("/void/{id}", response_model=ResponseSchema[StockDocumentOut])
async def void_stock_opening(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_opening:void"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0)],
    data: Annotated[VoidBody, Body()],
) -> JSONResponse:
    """按原流水冲销已确认业务。"""
    result = await StockOpeningService(auth, db).void(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockOpeningRouter.post("/delete", response_model=ResponseSchema[list[int]])
async def delete_stock_opening(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_opening:delete"]))], db: Annotated[AsyncSession, Depends(db_getter)], data: Annotated[DeleteBody, Body()]
) -> JSONResponse:
    """按版本批量软删除草稿。"""
    result = await StockOpeningService(auth, db).delete(data)
    return SuccessResponse(data=result)


@StockOpeningRouter.post("/export")
async def export_stock_opening(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_opening:export"]))], db: Annotated[AsyncSession, Depends(db_getter)], data: Annotated[DocumentExport, Body()]
) -> StreamingResponse:
    """按选定字段生成期初库存文件流并返回 UTF-8 下载名。"""
    content = await StockOpeningService(auth, db).export(data)
    media = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamResponse(
        data=bytes2file_response(content),
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename=stock_opening.{data.format}; filename*=UTF-8''{quote(data.download_name('期初库存'))}"},
    )

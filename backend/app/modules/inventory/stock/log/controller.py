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

from .schema import LogExport, LogOut, LogQuery
from .service import StockLogService

StockLogRouter = APIRouter(route_class=OperationLogRoute, prefix="/log", tags=["库存流水"])


@StockLogRouter.get("/list", response_model=ResponseSchema[PageResultSchema[LogOut]])
async def list_stock_log(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_log:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[LogQuery, Query()],
) -> JSONResponse:
    """分页查询库存流水，排序和筛选在服务层验证。"""
    result = await StockLogService(auth, db).page(page.page_no, page.page_size, search, page.order_by)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockLogRouter.get("/detail/{id}", response_model=ResponseSchema[LogOut])
async def detail_stock_log(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_log:detail"]))], db: Annotated[AsyncSession, Depends(db_getter)], id: Annotated[int, Path(gt=0)]
) -> JSONResponse:
    """读取库存流水详情并验证功能权限。"""
    result = await StockLogService(auth, db).detail(id)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockLogRouter.post("/export")
async def export_stock_log(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_log:export"]))], db: Annotated[AsyncSession, Depends(db_getter)], data: Annotated[LogExport, Body()]
) -> StreamingResponse:
    """按选定字段生成库存流水文件流并返回 UTF-8 下载名。"""
    content = await StockLogService(auth, db).export(data)
    media = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamResponse(
        data=bytes2file_response(content), media_type=media, headers={"Content-Disposition": f"attachment; filename=stock_log.{data.format}; filename*=UTF-8''{quote(data.download_name('库存流水'))}"}
    )

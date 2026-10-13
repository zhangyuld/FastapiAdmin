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

from .schema import BalanceExport, BalanceOut, BalanceQuery
from .service import StockBalanceService

StockBalanceRouter = APIRouter(route_class=OperationLogRoute, prefix="/balance", tags=["当前库存"])


@StockBalanceRouter.get("/list", response_model=ResponseSchema[PageResultSchema[BalanceOut]])
async def list_stock_balance(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_balance:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[BalanceQuery, Query()],
) -> JSONResponse:
    """分页查询当前库存，排序和筛选在服务层验证。"""
    result = await StockBalanceService(auth, db).page(page.page_no, page.page_size, search, page.order_by)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockBalanceRouter.get("/detail/{id}", response_model=ResponseSchema[BalanceOut])
async def detail_stock_balance(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_balance:detail"]))], db: Annotated[AsyncSession, Depends(db_getter)], id: Annotated[int, Path(gt=0)]
) -> JSONResponse:
    """读取当前库存详情并验证功能权限。"""
    result = await StockBalanceService(auth, db).detail(id)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockBalanceRouter.post("/export")
async def export_stock_balance(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_balance:export"]))], db: Annotated[AsyncSession, Depends(db_getter)], data: Annotated[BalanceExport, Body()]
) -> StreamingResponse:
    """按选定字段生成当前库存文件流并返回 UTF-8 下载名。"""
    content = await StockBalanceService(auth, db).export(data)
    media = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamResponse(
        data=bytes2file_response(content),
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename=stock_balance.{data.format}; filename*=UTF-8''{quote(data.download_name('当前库存'))}"},
    )

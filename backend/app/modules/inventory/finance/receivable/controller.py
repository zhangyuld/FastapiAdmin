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

from .schema import BalanceExport, BalanceOut, BalanceQuery, BillDetail, BillExport, BillOut, BillQuery, SummaryOut
from .service import ReceivableQueryService

ReceivableRouter = APIRouter(route_class=OperationLogRoute, prefix="/receivable", tags=["应收账款"])


@ReceivableRouter.get("/list", response_model=ResponseSchema[PageResultSchema[BillOut]])
async def list_receivable(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:receivable:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[BillQuery, Query()],
) -> JSONResponse:
    """分页读取应收账款账单，财务权限不受记账人数据范围截断。"""
    result = await ReceivableQueryService(auth, db).page(page.page_no, page.page_size, search, page.order_by)
    return SuccessResponse(data=result.model_dump(mode="json"))


@ReceivableRouter.get("/detail/{id}", response_model=ResponseSchema[BillDetail])
async def detail_receivable(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:receivable:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0)],
) -> JSONResponse:
    """读取账单及原账单/反向账单，来源业务需另行详情授权。"""
    result = await ReceivableQueryService(auth, db).detail(id)
    return SuccessResponse(data=result.model_dump(mode="json"))


@ReceivableRouter.get("/balance/list", response_model=ResponseSchema[PageResultSchema[BalanceOut]])
async def balances_receivable(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:receivable:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[BalanceQuery, Query()],
) -> JSONResponse:
    """按往来对象分页读取当前余额，不混入账单日期条件。"""
    result = await ReceivableQueryService(auth, db).balance_page(page.page_no, page.page_size, search, page.order_by)
    return SuccessResponse(data=result.model_dump(mode="json"))


@ReceivableRouter.get("/summary", response_model=ResponseSchema[SummaryOut])
async def summary_receivable(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:receivable:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    search: Annotated[BalanceQuery, Query()],
) -> JSONResponse:
    """汇总余额视图全部对象，正向余额与冲减余额分别统计。"""
    result = await ReceivableQueryService(auth, db).summary(search)
    return SuccessResponse(data=result.model_dump(mode="json"))


@ReceivableRouter.post("/export")
async def export_receivable(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:receivable:export"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[BillExport, Body()],
) -> StreamingResponse:
    """按当前账单筛选、字段顺序及文件选项导出。"""
    content = await ReceivableQueryService(auth, db).export(data)
    media = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamResponse(
        data=bytes2file_response(content), media_type=media, headers={"Content-Disposition": f"attachment; filename=receivable.{data.format}; filename*=UTF-8''{quote(data.download_name('应收账款'))}"}
    )


@ReceivableRouter.post("/balance/export")
async def export_receivable_balance(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:receivable:export"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[BalanceExport, Body()],
) -> StreamingResponse:
    """按对象余额导出，不复用账单字段或日期筛选。"""
    content = await ReceivableQueryService(auth, db).export(data)
    media = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamResponse(
        data=bytes2file_response(content),
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename=receivable_balance.{data.format}; filename*=UTF-8''{quote(data.download_name('应收账款余额'))}"},
    )

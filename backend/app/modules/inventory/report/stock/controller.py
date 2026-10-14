from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, Query, Security
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, StreamResponse, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute
from app.utils.common_util import bytes2file_response

from .schema import StockBalanceReportOut, StockBalanceReportSummary, StockMovementReportOut, StockMovementReportSummary, StockReportExport, StockReportQuery
from .service import StockReportService

StockReportRouter = APIRouter(route_class=OperationLogRoute, prefix="/stock", tags=["库存报表"])


@StockReportRouter.get("/list", response_model=ResponseSchema[PageResultSchema[StockBalanceReportOut | StockMovementReportOut]])
async def stock_report_list(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_report:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    search: Annotated[StockReportQuery, Query()],
    page: Annotated[PaginationQueryParam, Depends()],
) -> JSONResponse:
    """分页读取企业共享库存报表，余额和期间流水使用独立视图口径。"""
    result = await StockReportService(auth, db).page(search, page.page_no, page.page_size, page.order_by)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockReportRouter.get("/summary", response_model=ResponseSchema[StockBalanceReportSummary | StockMovementReportSummary])
async def stock_report_summary(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_report:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    search: Annotated[StockReportQuery, Query()],
) -> JSONResponse:
    """汇总全部筛选金额，不将期间净变动当作当前或期末库存。"""
    result = await StockReportService(auth, db).summary(search)
    return SuccessResponse(data=result.model_dump(mode="json"))


@StockReportRouter.post("/export")
async def stock_report_export(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:stock_report:export"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[StockReportExport, Body()],
) -> StreamingResponse:
    """按字段选择导出当前视图，默认文件名为库存报表加北京时间戳。"""
    content = await StockReportService(auth, db).export(data)
    media = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamResponse(
        data=bytes2file_response(content),
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename=stock_report.{data.format}; filename*=UTF-8''{quote(data.download_name())}"},
    )

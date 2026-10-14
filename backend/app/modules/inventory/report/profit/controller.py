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

from .schema import ProfitDocumentReportOut, ProfitGoodsReportOut, ProfitReportExport, ProfitReportQuery, ProfitReportSummary
from .service import ProfitReportService

ProfitReportRouter = APIRouter(route_class=OperationLogRoute, prefix="/profit", tags=["毛利报表"])


@ProfitReportRouter.get("/list", response_model=ResponseSchema[PageResultSchema[ProfitDocumentReportOut | ProfitGoodsReportOut]])
async def profit_report_list(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:profit_report:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    search: Annotated[ProfitReportQuery, Query()],
    page: Annotated[PaginationQueryParam, Depends()],
) -> JSONResponse:
    """按财务报表功能权限查询完整经营数据，不以创建人截断统计。"""
    result = await ProfitReportService(auth, db).page(search, page.page_no, page.page_size, page.order_by)
    return SuccessResponse(data=result.model_dump(mode="json"))


@ProfitReportRouter.get("/summary", response_model=ResponseSchema[ProfitReportSummary])
async def profit_report_summary(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:profit_report:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    search: Annotated[ProfitReportQuery, Query()],
) -> JSONResponse:
    """完整筛选金额重算汇总毛利率，净收入非正时返回空比例。"""
    result = await ProfitReportService(auth, db).summary(search)
    return SuccessResponse(data=result.model_dump(mode="json"))


@ProfitReportRouter.post("/export")
async def profit_report_export(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:profit_report:export"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[ProfitReportExport, Body()],
) -> StreamingResponse:
    """按用户字段顺序导出文件，默认文件名为毛利报表加时间戳。"""
    content = await ProfitReportService(auth, db).export(data)
    media = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamResponse(
        data=bytes2file_response(content), media_type=media, headers={"Content-Disposition": f"attachment; filename=profit_report.{data.format}; filename*=UTF-8''{quote(data.download_name())}"}
    )

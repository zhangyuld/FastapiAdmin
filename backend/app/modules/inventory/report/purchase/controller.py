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

from .schema import PurchaseDocumentReportOut, PurchaseGoodsReportOut, PurchaseReportExport, PurchaseReportQuery, PurchaseReportSummary
from .service import PurchaseReportService

PurchaseReportRouter = APIRouter(route_class=OperationLogRoute, prefix="/purchase", tags=["采购报表"])


@PurchaseReportRouter.get("/list", response_model=ResponseSchema[PageResultSchema[PurchaseDocumentReportOut | PurchaseGoodsReportOut]])
async def purchase_report_list(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_report:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    search: Annotated[PurchaseReportQuery, Query()],
    page: Annotated[PaginationQueryParam, Depends()],
) -> JSONResponse:
    """按财务报表功能权限查询完整经营数据，不以创建人截断统计。"""
    result = await PurchaseReportService(auth, db).page(search, page.page_no, page.page_size, page.order_by)
    return SuccessResponse(data=result.model_dump(mode="json"))


@PurchaseReportRouter.get("/summary", response_model=ResponseSchema[PurchaseReportSummary])
async def purchase_report_summary(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_report:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    search: Annotated[PurchaseReportQuery, Query()],
) -> JSONResponse:
    """按当前有效单据汇总，跨月退货计入退货单自身业务日期。"""
    result = await PurchaseReportService(auth, db).summary(search)
    return SuccessResponse(data=result.model_dump(mode="json"))


@PurchaseReportRouter.post("/export")
async def purchase_report_export(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_report:export"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[PurchaseReportExport, Body()],
) -> StreamingResponse:
    """按用户字段顺序导出文件，默认文件名为采购报表加时间戳。"""
    content = await PurchaseReportService(auth, db).export(data)
    media = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamResponse(
        data=bytes2file_response(content), media_type=media, headers={"Content-Disposition": f"attachment; filename=purchase_report.{data.format}; filename*=UTF-8''{quote(data.download_name())}"}
    )

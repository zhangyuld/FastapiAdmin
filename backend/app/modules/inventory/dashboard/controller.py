"""首页只读接口，由服务层按原领域权限裁剪和拒绝数据访问。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import DashboardSummary, RecentDocument, RecentQuery, StockWarningOut, TrendOut, TrendQuery, WarehouseStock, WarningQuery
from .service import DashboardService

DashboardRouter = APIRouter(route_class=OperationLogRoute, tags=["经营首页"])
Auth = Annotated[AuthSchema, Security(AuthPermission())]
Database = Annotated[AsyncSession, Depends(db_getter)]


@DashboardRouter.get("/summary", response_model=ResponseSchema[DashboardSummary])
async def dashboard_summary(auth: Auth, db: Database) -> JSONResponse:
    """返回登录用户可查看的指标，未授权领域为 null。"""
    return SuccessResponse(data=(await DashboardService(auth, db).summary()).model_dump(mode="json"))


@DashboardRouter.get("/trend", response_model=ResponseSchema[TrendOut])
async def dashboard_trend(auth: Auth, db: Database, query: Annotated[TrendQuery, Query()]) -> JSONResponse:
    """限定期间的逐日净采购、净销售趋势。"""
    return SuccessResponse(data=(await DashboardService(auth, db).trend(query.period)).model_dump(mode="json"))


@DashboardRouter.get("/warehouse-stock", response_model=ResponseSchema[list[WarehouseStock]])
async def dashboard_warehouses(auth: Auth, db: Database) -> JSONResponse:
    """当前库存金额按仓库分布。"""
    return SuccessResponse(data=[row.model_dump(mode="json") for row in await DashboardService(auth, db).warehouses()])


@DashboardRouter.get("/stock-warnings", response_model=ResponseSchema[PageResultSchema[StockWarningOut]])
async def dashboard_warnings(auth: Auth, db: Database, query: Annotated[WarningQuery, Query()]) -> JSONResponse:
    """当前低库存及超上限预警稳定分页。"""
    return SuccessResponse(data=(await DashboardService(auth, db).warnings(query)).model_dump(mode="json"))


@DashboardRouter.get("/recent-documents", response_model=ResponseSchema[list[RecentDocument]])
async def dashboard_recent(auth: Auth, db: Database, query: Annotated[RecentQuery, Query()]) -> JSONResponse:
    """原业务权限及数据范围内最近创建的采购销售单据。"""
    return SuccessResponse(data=[row.model_dump(mode="json") for row in await DashboardService(auth, db).recent(query.limit)])

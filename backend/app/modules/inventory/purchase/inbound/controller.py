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

from .schema import (
    PurchaseInConfirmSchema,
    PurchaseInCreateSchema,
    PurchaseInDeleteSchema,
    PurchaseInDetailOutSchema,
    PurchaseInExportSchema,
    PurchaseInOutSchema,
    PurchaseInQueryParam,
    PurchaseInRelatedReturnOutSchema,
    PurchaseInReturnableOutSchema,
    PurchaseInReturnableQueryParam,
    PurchaseInUpdateSchema,
    PurchaseInVoidSchema,
)
from .service import PurchaseInService

PurchaseInRouter = APIRouter(route_class=OperationLogRoute, prefix="/inbound", tags=["采购入库"])


@PurchaseInRouter.get("/returns/{id}", summary="分页查询入库关联退货", response_model=ResponseSchema[PageResultSchema[PurchaseInRelatedReturnOutSchema]])
async def get_purchase_in_returns_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_return:query"]))],
    source_auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_in:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0, description="采购入库单ID")],
    page: Annotated[PaginationQueryParam, Depends()],
) -> JSONResponse:
    """同时要求入库详情和退货查询权限，原单和退货均执行数据范围校验。"""
    result = await PurchaseInService(auth, db).related_returns(id, page.page_no, page.page_size)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="查询关联退货成功")


@PurchaseInRouter.post("/confirm/{id}", summary="确认采购入库", response_model=ResponseSchema[PurchaseInDetailOutSchema])
async def confirm_purchase_in_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_in:confirm"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0, description="采购入库单ID")],
    data: Annotated[PurchaseInConfirmSchema, Body(description="当前单据版本")],
) -> JSONResponse:
    """按版本确认采购草稿，库存和应付在同一请求事务中入账。"""
    result = await PurchaseInService(auth, db).confirm(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="确认采购入库成功")


@PurchaseInRouter.post("/void/{id}", summary="作废采购入库", response_model=ResponseSchema[PurchaseInDetailOutSchema])
async def void_purchase_in_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_in:void"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0, description="采购入库单ID")],
    data: Annotated[PurchaseInVoidSchema, Body(description="当前版本与作废原因")],
) -> JSONResponse:
    """生成原入账记录的反向流水，不能删除历史库存和应付。"""
    result = await PurchaseInService(auth, db).void(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="作废采购入库成功")


@PurchaseInRouter.get("/returnable/{id}", summary="查询采购入库可退数量", response_model=ResponseSchema[PurchaseInReturnableOutSchema])
async def get_purchase_in_returnable_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_in:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0, description="来源采购入库单ID")],
    query: Annotated[PurchaseInReturnableQueryParam, Query()],
) -> JSONResponse:
    """沿用入库详情权限，已确认退货扣减数量，草稿不占用。"""
    result = await PurchaseInService(auth, db).returnable(id, query)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="查询采购入库可退数量成功")


@PurchaseInRouter.get("/list", summary="分页查询采购入库", response_model=ResponseSchema[PageResultSchema[PurchaseInOutSchema]])
async def get_purchase_in_list_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_in:query"]))],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[PurchaseInQueryParam, Query()],
    db: Annotated[AsyncSession, Depends(db_getter)],
) -> JSONResponse:
    """绑定分页和查询参数，返回不含明细的主单列表。"""
    result = await PurchaseInService(auth, db).page(page_no=page.page_no, page_size=page.page_size, search=search, order_by=page.order_by)
    # SuccessResponse 默认先执行 Python 模式 dump，显式 JSON dump 才能保留 Decimal 的字段序列化。
    return SuccessResponse(data=result.model_dump(mode="json"), msg="查询采购入库列表成功")


@PurchaseInRouter.get("/detail/{id}", summary="查询采购入库详情", response_model=ResponseSchema[PurchaseInDetailOutSchema])
async def get_purchase_in_detail_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_in:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0, description="采购入库单ID")],
) -> JSONResponse:
    """按详情权限返回主单、商品快照和审计信息。"""
    result = await PurchaseInService(auth, db).detail(id)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="查询采购入库详情成功")


@PurchaseInRouter.post("/create", status_code=status.HTTP_201_CREATED, summary="创建采购入库草稿", response_model=ResponseSchema[PurchaseInDetailOutSchema])
async def create_purchase_in_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_in:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[PurchaseInCreateSchema, Body(description="采购入库草稿")],
) -> JSONResponse:
    """创建主从表草稿，不执行库存和应付入账。"""
    result = await PurchaseInService(auth, db).create(data)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="创建采购入库草稿成功", status_code=status.HTTP_201_CREATED)


@PurchaseInRouter.post("/update/{id}", summary="修改采购入库草稿", response_model=ResponseSchema[PurchaseInDetailOutSchema])
async def update_purchase_in_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_in:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0, description="采购入库单ID")],
    data: Annotated[PurchaseInUpdateSchema, Body(description="完整草稿及当前版本")],
) -> JSONResponse:
    """按版本替换草稿内容，业务层校验状态并保持单号不变。"""
    result = await PurchaseInService(auth, db).update(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="修改采购入库草稿成功")


@PurchaseInRouter.post("/delete", summary="删除采购入库草稿", response_model=ResponseSchema[list[int]])
async def delete_purchase_in_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_in:delete"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[PurchaseInDeleteSchema, Body(description="草稿ID及版本映射")],
) -> JSONResponse:
    """批量软删除草稿，失败时请求事务整体回滚。"""
    result = await PurchaseInService(auth, db).delete(data)
    return SuccessResponse(data=result, msg="删除采购入库草稿成功")


@PurchaseInRouter.post("/export", summary="导出采购入库列表")
async def export_purchase_in_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_in:export"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[PurchaseInExportSchema, Body(description="查询、字段及导出文件参数")],
) -> StreamingResponse:
    """生成选定字段的文件流，中文下载名采用 UTF-8 编码。"""
    content = await PurchaseInService(auth, db).export(data)
    media_type = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamResponse(
        data=bytes2file_response(content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=purchase_in.{data.format}; filename*=UTF-8''{quote(data.get_download_filename())}"},
    )

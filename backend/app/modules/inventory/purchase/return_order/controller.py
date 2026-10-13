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
    PurchaseReturnConfirmSchema,
    PurchaseReturnCreateSchema,
    PurchaseReturnDeleteSchema,
    PurchaseReturnDetailOutSchema,
    PurchaseReturnExportSchema,
    PurchaseReturnOutSchema,
    PurchaseReturnQueryParam,
    PurchaseReturnUpdateSchema,
    PurchaseReturnVoidSchema,
)
from .service import PurchaseReturnService

PurchaseReturnRouter = APIRouter(route_class=OperationLogRoute, prefix="/return_order", tags=["采购退货"])


@PurchaseReturnRouter.get("/list", summary="分页查询采购退货", response_model=ResponseSchema[PageResultSchema[PurchaseReturnOutSchema]])
async def list_purchase_return_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_return:query"]))],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[PurchaseReturnQueryParam, Query()],
    db: Annotated[AsyncSession, Depends(db_getter)],
) -> JSONResponse:
    """绑定筛选、分页及数据权限，列表不加载明细。"""
    result = await PurchaseReturnService(auth, db).page(page.page_no, page.page_size, search, page.order_by)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="查询采购退货列表成功")


@PurchaseReturnRouter.get("/detail/{id}", summary="查询采购退货详情", response_model=ResponseSchema[PurchaseReturnDetailOutSchema])
async def detail_purchase_return_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_return:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0)],
) -> JSONResponse:
    """返回来源快照、成本和状态审计信息。"""
    result = await PurchaseReturnService(auth, db).detail(id)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="查询采购退货详情成功")


@PurchaseReturnRouter.post("/create", status_code=status.HTTP_201_CREATED, summary="创建原单采购退货草稿", response_model=ResponseSchema[PurchaseReturnDetailOutSchema])
async def create_purchase_return_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_return:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[PurchaseReturnCreateSchema, Body()],
) -> JSONResponse:
    """保存原单退货草稿，禁止缺少来源或客户端提交成本。"""
    result = await PurchaseReturnService(auth, db).create(data)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="创建采购退货草稿成功", status_code=status.HTTP_201_CREATED)


@PurchaseReturnRouter.post("/update/{id}", summary="修改采购退货草稿", response_model=ResponseSchema[PurchaseReturnDetailOutSchema])
async def update_purchase_return_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_return:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0)],
    data: Annotated[PurchaseReturnUpdateSchema, Body()],
) -> JSONResponse:
    """按当前版本完整替换草稿，可切换已确认来源。"""
    result = await PurchaseReturnService(auth, db).update(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="修改采购退货草稿成功")


@PurchaseReturnRouter.post("/delete", summary="删除采购退货草稿", response_model=ResponseSchema[list[int]])
async def delete_purchase_return_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_return:delete"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[PurchaseReturnDeleteSchema, Body()],
) -> JSONResponse:
    """按 ID 和版本整批软删除，任一步失败全部回滚。"""
    result = await PurchaseReturnService(auth, db).delete(data)
    return SuccessResponse(data=result, msg="删除采购退货草稿成功")


@PurchaseReturnRouter.post("/confirm/{id}", summary="确认采购退货", response_model=ResponseSchema[PurchaseReturnDetailOutSchema])
async def confirm_purchase_return_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_return:confirm"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0)],
    data: Annotated[PurchaseReturnConfirmSchema, Body()],
) -> JSONResponse:
    """锁来源和库存后扣减余额、固化成本并冲减应付。"""
    result = await PurchaseReturnService(auth, db).confirm(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="确认采购退货成功")


@PurchaseReturnRouter.post("/void/{id}", summary="作废采购退货", response_model=ResponseSchema[PurchaseReturnDetailOutSchema])
async def void_purchase_return_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_return:void"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0)],
    data: Annotated[PurchaseReturnVoidSchema, Body()],
) -> JSONResponse:
    """冲销原退货流水和应付，原记录永久保留。"""
    result = await PurchaseReturnService(auth, db).void(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="作废采购退货成功")


@PurchaseReturnRouter.post("/export", summary="导出采购退货列表")
async def export_purchase_return_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:purchase_return:export"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[PurchaseReturnExportSchema, Body()],
) -> StreamingResponse:
    """按字段白名单输出文件流，文件名支持中文和默认时间戳。"""
    content = await PurchaseReturnService(auth, db).export(data)
    media_type = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamResponse(
        data=bytes2file_response(content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=purchase_return.{data.format}; filename*=UTF-8''{quote(data.get_download_filename())}"},
    )

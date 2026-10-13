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
    SaleOutConfirmSchema,
    SaleOutCreateSchema,
    SaleOutDeleteSchema,
    SaleOutDetailOutSchema,
    SaleOutExportSchema,
    SaleOutOutSchema,
    SaleOutQueryParam,
    SaleOutRelatedReturnOutSchema,
    SaleOutReturnableOutSchema,
    SaleOutReturnableQueryParam,
    SaleOutUpdateSchema,
    SaleOutVoidSchema,
)
from .service import SaleOutService

SaleOutRouter = APIRouter(route_class=OperationLogRoute, prefix="/out", tags=["销售出库"])


@SaleOutRouter.get("/returns/{id}", summary="分页查询出库关联退货", response_model=ResponseSchema[PageResultSchema[SaleOutRelatedReturnOutSchema]])
async def get_sale_out_returns_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:sale_return:query"]))],
    source_auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:sale_out:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0, description="销售出库单ID")],
    page: Annotated[PaginationQueryParam, Depends()],
) -> JSONResponse:
    """同时要求出库详情和退货查询权限，原单和退货均执行数据范围校验。"""
    result = await SaleOutService(auth, db).related_returns(id, page.page_no, page.page_size)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="查询关联退货成功")


@SaleOutRouter.post("/confirm/{id}", summary="确认销售出库", response_model=ResponseSchema[SaleOutDetailOutSchema])
async def confirm_sale_out_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:sale_out:confirm"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0, description="销售出库单ID")],
    data: Annotated[SaleOutConfirmSchema, Body(description="当前单据版本")],
) -> JSONResponse:
    """按版本确认销售草稿，库存和应收在同一请求事务中入账。"""
    result = await SaleOutService(auth, db).confirm(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="确认销售出库成功")


@SaleOutRouter.post("/void/{id}", summary="作废销售出库", response_model=ResponseSchema[SaleOutDetailOutSchema])
async def void_sale_out_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:sale_out:void"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0, description="销售出库单ID")],
    data: Annotated[SaleOutVoidSchema, Body(description="当前版本与作废原因")],
) -> JSONResponse:
    """生成原入账记录的反向流水，不能删除历史库存和应收。"""
    result = await SaleOutService(auth, db).void(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="作废销售出库成功")


@SaleOutRouter.get("/returnable/{id}", summary="查询销售出库可退数量", response_model=ResponseSchema[SaleOutReturnableOutSchema])
async def get_sale_out_returnable_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:sale_out:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0, description="来源销售出库单ID")],
    query: Annotated[SaleOutReturnableQueryParam, Query()],
) -> JSONResponse:
    """沿用出库详情权限，已确认退货扣减数量，草稿不占用。"""
    result = await SaleOutService(auth, db).returnable(id, query)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="查询销售出库可退数量成功")


@SaleOutRouter.get("/list", summary="分页查询销售出库", response_model=ResponseSchema[PageResultSchema[SaleOutOutSchema]])
async def get_sale_out_list_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:sale_out:query"]))],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[SaleOutQueryParam, Query()],
    db: Annotated[AsyncSession, Depends(db_getter)],
) -> JSONResponse:
    """绑定分页和查询参数，返回不含明细的主单列表。"""
    result = await SaleOutService(auth, db).page(page_no=page.page_no, page_size=page.page_size, search=search, order_by=page.order_by)
    # SuccessResponse 默认先执行 Python 模式 dump，显式 JSON dump 才能保留 Decimal 的字段序列化。
    return SuccessResponse(data=result.model_dump(mode="json"), msg="查询销售出库列表成功")


@SaleOutRouter.get("/detail/{id}", summary="查询销售出库详情", response_model=ResponseSchema[SaleOutDetailOutSchema])
async def get_sale_out_detail_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:sale_out:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0, description="销售出库单ID")],
) -> JSONResponse:
    """按详情权限返回主单、商品快照和审计信息。"""
    result = await SaleOutService(auth, db).detail(id)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="查询销售出库详情成功")


@SaleOutRouter.post("/create", status_code=status.HTTP_201_CREATED, summary="创建销售出库草稿", response_model=ResponseSchema[SaleOutDetailOutSchema])
async def create_sale_out_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:sale_out:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[SaleOutCreateSchema, Body(description="销售出库草稿")],
) -> JSONResponse:
    """创建主从表草稿，不执行库存和应收入账。"""
    result = await SaleOutService(auth, db).create(data)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="创建销售出库草稿成功", status_code=status.HTTP_201_CREATED)


@SaleOutRouter.post("/update/{id}", summary="修改销售出库草稿", response_model=ResponseSchema[SaleOutDetailOutSchema])
async def update_sale_out_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:sale_out:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(gt=0, description="销售出库单ID")],
    data: Annotated[SaleOutUpdateSchema, Body(description="完整草稿及当前版本")],
) -> JSONResponse:
    """按版本替换草稿内容，业务层校验状态并保持单号不变。"""
    result = await SaleOutService(auth, db).update(id, data)
    return SuccessResponse(data=result.model_dump(mode="json"), msg="修改销售出库草稿成功")


@SaleOutRouter.post("/delete", summary="删除销售出库草稿", response_model=ResponseSchema[list[int]])
async def delete_sale_out_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:sale_out:delete"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[SaleOutDeleteSchema, Body(description="草稿ID及版本映射")],
) -> JSONResponse:
    """批量软删除草稿，失败时请求事务整体回滚。"""
    result = await SaleOutService(auth, db).delete(data)
    return SuccessResponse(data=result, msg="删除销售出库草稿成功")


@SaleOutRouter.post("/export", summary="导出销售出库列表")
async def export_sale_out_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:sale_out:export"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[SaleOutExportSchema, Body(description="查询、字段及导出文件参数")],
) -> StreamingResponse:
    """生成选定字段的文件流，中文下载名采用 UTF-8 编码。"""
    content = await SaleOutService(auth, db).export(data)
    media_type = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamResponse(
        data=bytes2file_response(content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=sale_out.{data.format}; filename*=UTF-8''{quote(data.get_download_filename())}"},
    )

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, StreamResponse, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute
from app.utils.common_util import bytes2file_response

from .schema import GoodsCreateSchema, GoodsDeleteSchema, GoodsExportSchema, GoodsOutSchema, GoodsQueryParam
from .service import GoodsService

GoodsRouter = APIRouter(route_class=OperationLogRoute, prefix="/goods", tags=["商品管理"])


@GoodsRouter.get("/detail/{id}", summary="查询商品详情", response_model=ResponseSchema[GoodsOutSchema])
async def get_goods_detail_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:goods:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="商品ID", ge=1)],
) -> JSONResponse:
    result = await GoodsService(auth, db).detail(id=id)
    return SuccessResponse(data=result, msg="查询商品详情成功")

@GoodsRouter.get("/list", summary="分页查询商品列表", response_model=ResponseSchema[PageResultSchema[GoodsOutSchema]])
async def get_goods_list_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:goods:query"]))],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[GoodsQueryParam, Query()],
    db: Annotated[AsyncSession, Depends(db_getter)],
) -> JSONResponse:
    result: PageResultSchema[GoodsOutSchema] = await GoodsService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="分页查询商品列表成功")


@GoodsRouter.post("/create", status_code=status.HTTP_201_CREATED, summary="创建商品", response_model=ResponseSchema[GoodsOutSchema])
async def create_goods_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:goods:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[GoodsCreateSchema, Body(description="商品创建参数")],
) -> JSONResponse:
    result = await GoodsService(auth, db).create(data=data)
    return SuccessResponse(data=result, msg="创建商品成功")

@GoodsRouter.post('/update/{id}', summary="修改商品", response_model=ResponseSchema[GoodsOutSchema])
async def update_goods_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:goods:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="商品ID", ge=1)],
    data: Annotated[GoodsCreateSchema, Body(description="商品更新参数")],
) -> JSONResponse:
    result = await GoodsService(auth, db).update(id=id, data=data)
    return SuccessResponse(data=result, msg="修改商品成功")

@GoodsRouter.post('/delete', summary="删除商品", response_model=ResponseSchema[list[int]])
async def delete_goods_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:goods:delete"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[GoodsDeleteSchema, Body(description="商品删除参数")],
) -> JSONResponse:
    result = await GoodsService(auth, db).delete(data=data)
    return SuccessResponse(data=result, msg="删除商品成功")

@GoodsRouter.post('/export', summary="导出商品")
async def export_goods_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:goods:export"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[GoodsExportSchema, Body()],
) -> StreamingResponse:
    result = await GoodsService(auth, db).export(data=data)
    media_type = "text/csv; charset=utf-8" if data.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamResponse(
        data=bytes2file_response(result),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=goods.{data.format}"},
    )

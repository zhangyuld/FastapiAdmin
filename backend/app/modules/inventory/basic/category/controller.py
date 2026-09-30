from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path, Query, Security, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, BatchSetAvailable
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import (
    GoodsCategoryCreateSchema,
    GoodsCategoryOutSchema,
    GoodsCategoryQueryParam,
    GoodsCategoryTreeOutSchema,
    GoodsCategoryUpdateSchema,
)
from .service import GoodsCategoryService

GoodsCategoryRouter = APIRouter(route_class=OperationLogRoute, prefix="/category", tags=["商品分类"])


@GoodsCategoryRouter.get("/tree", summary="查询商品分类树", response_model=ResponseSchema[list[GoodsCategoryTreeOutSchema]])
async def get_goods_category_tree_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:category:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    search: Annotated[GoodsCategoryQueryParam, Query()],
) -> JSONResponse:
    result: list[dict[str, Any]] = await GoodsCategoryService(auth, db).tree(search=search)
    return SuccessResponse(data=result, msg="查询商品分类树成功")


@GoodsCategoryRouter.get("/detail/{id}", summary="查询商品分类详情", response_model=ResponseSchema[GoodsCategoryOutSchema])
async def get_goods_category_detail_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:category:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="商品分类ID", ge=1)],
) -> JSONResponse:
    result = await GoodsCategoryService(auth, db).detail(id=id)
    return SuccessResponse(data=result, msg="查询商品分类详情成功")


@GoodsCategoryRouter.post("/create", status_code=status.HTTP_201_CREATED, summary="创建商品分类", response_model=ResponseSchema[GoodsCategoryOutSchema])
async def create_goods_category_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:category:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[GoodsCategoryCreateSchema, Body(description="商品分类创建参数")],
) -> JSONResponse:
    result = await GoodsCategoryService(auth, db).create(data=data)
    return SuccessResponse(data=result, msg="创建商品分类成功")


@GoodsCategoryRouter.put("/update/{id}", summary="修改商品分类", response_model=ResponseSchema[GoodsCategoryOutSchema])
async def update_goods_category_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:category:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="商品分类ID", ge=1)],
    data: Annotated[GoodsCategoryUpdateSchema, Body(description="商品分类修改参数")],
) -> JSONResponse:
    result = await GoodsCategoryService(auth, db).update(id=id, data=data)
    return SuccessResponse(data=result, msg="修改商品分类成功")


@GoodsCategoryRouter.delete("/delete", summary="删除商品分类", response_model=ResponseSchema[None])
async def delete_goods_category_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:category:delete"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    ids: Annotated[list[int], Body(description="商品分类ID列表")],
) -> JSONResponse:
    await GoodsCategoryService(auth, db).delete(ids=ids)
    return SuccessResponse(msg="删除商品分类成功")


@GoodsCategoryRouter.patch("/status/batch", summary="批量修改商品分类状态", response_model=ResponseSchema[None])
async def batch_set_goods_category_status_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_inventory:category:patch"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[BatchSetAvailable, Body(description="商品分类状态设置")],
) -> JSONResponse:
    await GoodsCategoryService(auth, db).set_available(data=data)
    return SuccessResponse(msg="批量修改商品分类状态成功")

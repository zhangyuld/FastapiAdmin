"""登录用户读取裁剪配置，超管发布完整默认值及功能策略。"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, Security
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.config.setting import settings
from app.core.base_schema import AuthSchema
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .docs import DOCS_COOKIE, docs_auth
from .schema import ProductConfig
from .service import ProductConfigService

ProductConfigRouter = APIRouter(prefix="/product-config", route_class=OperationLogRoute, tags=["产品配置"])
Auth = Annotated[AuthSchema, Security(AuthPermission())]
Database = Annotated[AsyncSession, Depends(db_getter)]


@ProductConfigRouter.get("/profile")
async def get_product_profile(auth: Auth, db: Database) -> JSONResponse:
    """按身份裁剪配置，普通用户不接收任何专属内容。"""
    return SuccessResponse(data=await ProductConfigService(db).profile(auth))


@ProductConfigRouter.get("/detail", response_model=ResponseSchema[ProductConfig])
async def get_product_config(auth: Auth, db: Database) -> JSONResponse:
    """完整策略只有超管可查看。"""
    ProductConfigService.require_superuser(auth)
    return SuccessResponse(data=(await ProductConfigService(db).read()).model_dump(mode="json"))


@ProductConfigRouter.post("/publish", response_model=ResponseSchema[ProductConfig])
async def publish_product_config(auth: Auth, db: Database, data: Annotated[ProductConfig, Body()]) -> JSONResponse:
    """发布白名单设置及可扩展策略，不接收运行状态。"""
    return SuccessResponse(data=(await ProductConfigService(db).publish(auth, data)).model_dump(mode="json"))


@ProductConfigRouter.post("/docs-session")
async def create_docs_session(auth: Auth, db: Database, request: Request) -> JSONResponse:
    """建立五分钟文档访问 cookie，仅绑定现有可撤销的访问令牌。"""
    ProductConfigService.require_superuser(auth)
    await ProductConfigService(db).require_feature("api_docs", auth)
    response = SuccessResponse(data={"url": f"{settings.ROOT_PATH}/system/product-config/docs"})
    response.set_cookie(DOCS_COOKIE, request.headers.get("authorization", ""), max_age=300, httponly=True, secure=request.url.scheme == "https", samesite="strict")
    return response


@ProductConfigRouter.get("/docs", dependencies=[Depends(docs_auth)], include_in_schema=False)
async def product_docs() -> HTMLResponse:
    """同源 iframe 文档，schema 读取也必须通过专属认证。"""
    return get_swagger_ui_html(openapi_url=f"{settings.ROOT_PATH}/system/product-config/openapi", title="智仓云接口文档", swagger_js_url=settings.SWAGGER_JS_URL, swagger_css_url=settings.SWAGGER_CSS_URL)


@ProductConfigRouter.get("/openapi", dependencies=[Depends(docs_auth)], include_in_schema=False)
async def product_openapi(request: Request) -> JSONResponse:
    """返回原应用完整 schema，不提供匿名绕过入口。"""
    return JSONResponse(request.app.openapi())

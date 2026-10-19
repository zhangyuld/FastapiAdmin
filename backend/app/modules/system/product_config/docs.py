"""接口文档以短期 HttpOnly cookie 支持 iframe，不将令牌写入 URL。"""

from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema
from app.core.dependencies import db_getter, get_current_user, redis_getter

from .service import ProductConfigService

DOCS_COOKIE = "zhicang_docs"


async def docs_auth(request: Request, db: Annotated[AsyncSession, Depends(db_getter)], redis: Annotated[Redis, Depends(redis_getter)]) -> AuthSchema:
    """每次文档访问重新认证并校验超管与功能状态，退出令牌立即失效。"""
    token = request.headers.get("authorization") or request.cookies.get(DOCS_COOKIE, "")
    auth = await get_current_user(db=db, redis=redis, token=token)
    ProductConfigService.require_superuser(auth)
    await ProductConfigService(db).require_feature("api_docs", auth)
    return auth

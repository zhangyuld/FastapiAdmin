"""智仓云发布版本、策略裁剪、匿名缓存、旧认证入口及文档访问回归。"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.base_schema import AuthSchema, CoreUserSchema
from app.core.database import async_db_session
from app.core.dependencies import get_current_user
from app.modules.system.menu.schema import MenuOutSchema
from app.modules.system.params.model import ParamsModel
from app.modules.system.product_config.crud import PRODUCT_CONFIG_KEY
from app.modules.system.product_config.schema import FeatureRule, ProductConfig
from app.modules.system.product_config.service import ProductConfigService, path_matches

PREFIX = "/system/product-config"


@pytest.fixture(autouse=True)
def configuration_baseline(test_client):
    """每项测试恢复配置版本，不向开发数据库发布测试策略。"""
    async def prepare():
        async with async_db_session() as db, db.begin():
            service = ProductConfigService(db)
            await service.initialize()
            return (await service.row()).config_value

    async def restore(value):
        async with async_db_session() as db, db.begin():
            row = await db.scalar(select(ParamsModel).where(ParamsModel.config_key == PRODUCT_CONFIG_KEY))
            row.config_value = value
            row.status = 0

    baseline = test_client.portal.call(prepare)
    test_client.cookies.clear()
    with patch("app.core.router_class._write_operation_log_async", new=AsyncMock()):
        yield
    test_client.portal.call(restore, baseline)
    test_client.cookies.clear()


@pytest.fixture
def ordinary(test_client):
    """模拟非超管拥有旧模块权限及通配权限，也不能访问专属功能。"""
    auth = AuthSchema(user=CoreUserSchema(id=3, username="user", is_superuser=False), permissions=["*:*:*", "module_ai:chat:query", "module_monitor:server:query", "module_task:job:query", "module_generator:gencode:query", "module_system:param:update"])
    old = test_client.app.dependency_overrides.get(get_current_user)
    test_client.app.dependency_overrides[get_current_user] = lambda: auth
    yield auth
    if old is None:
        test_client.app.dependency_overrides.pop(get_current_user, None)
    else:
        test_client.app.dependency_overrides[get_current_user] = old


def result(client, headers, endpoint):
    """成功响应保持正式接口格式。"""
    response = client.get(PREFIX + endpoint, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_confirmed_defaults(test_client, auth_headers):
    """首版默认值来自用户确认配置，不依赖操作系统暗色偏好。"""
    config = result(test_client, auth_headers, "/detail")
    settings = config["settings"]
    assert settings["menuOpenWidth"] == 220
    assert settings["systemThemeMode"] == settings["systemThemeType"] == "light"
    assert settings["menuThemeType"] == "light" and settings["systemThemeColor"] == "#5D87FF"
    assert settings["watermarkVisible"] and not settings["boxBorderMode"]
    assert not settings["showLanguage"] and not settings["showGuide"]
    assert "refresh" not in settings and "festivalDate" not in settings


def test_ordinary_profile_strips_exclusive_settings(test_client, ordinary):
    """快速入口即使开启也不下发普通用户，完整策略接口另行拒绝。"""
    profile = result(test_client, {}, "/profile")
    assert "showFastEnter" not in profile["settings"]
    assert "userEnableAi" not in profile["settings"]
    assert profile["capabilities"] == {} and "quick_links" not in profile
    assert "features" not in profile
    assert test_client.get(PREFIX + "/detail").status_code == 403
    assert test_client.post(PREFIX + "/publish", json=ProductConfig().model_dump()).status_code == 403


def test_superuser_receives_quick_links(test_client, auth_headers):
    """仓库链接从头像菜单转为后端下发的超管入口。"""
    profile = result(test_client, auth_headers, "/profile")
    assert profile["capabilities"]["quick_entry"]
    assert {link["name"] for link in profile["quick_links"]} == {"GitHub", "Gitee"}


def test_publish_is_versioned_and_old_revision_rejected(test_client, auth_headers):
    """并发编辑使用版本比较更新，过期草稿不能覆盖发布。"""
    config = result(test_client, auth_headers, "/detail")
    config["settings"]["menuOpenWidth"] = 240
    response = test_client.post(PREFIX + "/publish", headers=auth_headers, json=config)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["revision"] == config["revision"] + 1
    assert result(test_client, auth_headers, "/profile")["settings"]["menuOpenWidth"] == 240
    assert test_client.post(PREFIX + "/publish", headers=auth_headers, json=config).status_code == 409


def test_additional_policy_controls_setting_and_api(test_client, auth_headers):
    """扩展新专属项无需增加前端角色名单，设置及接口由后端策略裁剪。"""
    config = result(test_client, auth_headers, "/detail")
    config["features"].append(FeatureRule(key="warehouse_tools", label="仓库工具", api_prefixes=["/inventory/basic/warehouse"], setting_keys=["showFullscreen"]).model_dump())
    assert test_client.post(PREFIX + "/publish", headers=auth_headers, json=config).status_code == 200
    async def check():
        async with async_db_session() as db:
            service = ProductConfigService(db)
            auth = AuthSchema(user=CoreUserSchema(id=3, is_superuser=False))
            assert "showFullscreen" not in (await service.profile(auth))["settings"]
            from app.core.exceptions import CustomException
            with pytest.raises(CustomException):
                await service.require_path("/inventory/basic/warehouse/list", auth)
    test_client.portal.call(check)


@pytest.mark.parametrize("url", ["/ai/chat/list", "/monitor/server/info", "/monitor/health/check", "/task/cronjob/job/scheduler/status", "/generator/gencode/list"])
def test_old_permissions_cannot_bypass_superuser_policy(test_client, ordinary, url):
    """隐藏菜单之外还拒绝直接调用五类模块接口。"""
    response = test_client.get(url)
    assert response.status_code == 403, response.text


def test_disabled_feature_denies_superuser(test_client, auth_headers):
    """专属功能停用对超管也生效，不绕过策略 enabled。"""
    config = result(test_client, auth_headers, "/detail")
    next(rule for rule in config["features"] if rule["key"] == "ai")["enabled"] = False
    assert test_client.post(PREFIX + "/publish", headers=auth_headers, json=config).status_code == 200
    assert "ai" not in result(test_client, auth_headers, "/profile")["capabilities"]
    assert test_client.get("/ai/chat/list", headers=auth_headers).status_code == 403


def test_private_param_never_leaks_through_anonymous_cache(test_client):
    """历史 Redis 中已有私有记录也必须过滤，不能只过滤新写入缓存。"""
    with patch("app.core.redis_crud.RedisCURD.get_keys", new=AsyncMock(return_value=["key"])), patch("app.core.redis_crud.RedisCURD.mget", new=AsyncMock(return_value=[json.dumps({"config_key": PRODUCT_CONFIG_KEY, "config_value": "private"})])):
        response = test_client.get("/system/param/info")
        assert response.status_code == 200, response.text
        assert PRODUCT_CONFIG_KEY not in response.text


def test_generic_parameter_update_cannot_bypass_publisher(test_client, auth_headers):
    async def identifier():
        async with async_db_session() as db:
            return (await ProductConfigService(db).row()).id
    id = test_client.portal.call(identifier)
    response = test_client.put(f"/system/param/update/{id}", headers=auth_headers, json={"config_key": PRODUCT_CONFIG_KEY, "config_value": "{}", "config_name": "private", "status": 0, "config_type": True})
    assert response.status_code == 403, response.text


def test_menu_parent_removal_covers_relative_children(test_client):
    async def check():
        async with async_db_session() as db:
            auth = AuthSchema(user=CoreUserSchema(id=3, is_superuser=False))
            menus = [MenuOutSchema.model_construct(id=1, name="AI", type=1, order=1, route_path="/ai"), MenuOutSchema.model_construct(id=2, name="relative", type=2, order=1, route_path="chat", parent_id=1), MenuOutSchema.model_construct(id=3, name="商品", type=2, order=1, route_path="/inventory/basic/goods"), MenuOutSchema.model_construct(id=4, name="定价", type=2, order=1, route_path="/fastlink/pricing")]
            filtered = await ProductConfigService(db).filter_menus(menus, auth)
            assert [menu.id for menu in filtered] == [3]
    test_client.portal.call(check)


@pytest.mark.parametrize("url", ["/system/auth/oauth/github/login", "/system/auth/oauth/github/callback", "/system/auth/wx-login", "/system/auth/wx-phone-login", "/system/auth/wx-qrcode/generate"])
def test_account_only_routes_are_not_registered(test_client, url):
    assert not any(getattr(route, "path", "").startswith(("/system/auth/oauth", "/system/auth/wx-")) for route in test_client.app.routes)
    method = "get" if "/oauth/" in url else "post"
    response = getattr(test_client, method)(url)
    assert response.status_code in (200, 404, 405)
    if response.status_code == 200:
        assert "text/html" in response.headers.get("content-type", "")


def test_docs_schema_requires_authentication(test_client, auth_headers):
    for path in ("/docs", "/redoc", "/openapi.json", PREFIX + "/openapi"):
        assert test_client.get(path).status_code == 401
    assert test_client.get("/openapi.json", headers=auth_headers).status_code == 200
    response = test_client.post(PREFIX + "/docs-session", headers=auth_headers)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Max-Age=300" in cookie and "SameSite=strict" in cookie
    assert test_client.get(PREFIX + "/docs").status_code == 200


@pytest.mark.parametrize("mutation", ["runtime", "missing", "weaken", "duplicate", "script_link"])
def test_invalid_configuration_rejected(mutation):
    data = ProductConfig().model_dump()
    if mutation == "runtime":
        data["settings"]["refresh"] = True
    elif mutation == "missing":
        data["features"].pop()
    elif mutation == "weaken":
        data["features"][2]["api_prefixes"] = []
    elif mutation == "duplicate":
        data["features"].append(data["features"][0])
    else:
        data["quick_links"][0]["link"] = "javascript:alert(1)"
    with pytest.raises(ValidationError):
        ProductConfig.model_validate(data)


def test_segment_boundary_match():
    assert path_matches("/ai/chat/list", "/ai")
    assert not path_matches("/ai-example/chat", "/ai")


def test_disabled_captcha_has_explicit_switch(test_client):
    """关闭验证码与获取异常分开，前端无需将异常降级为免验证。"""
    with patch("app.modules.system.auth.service.settings.CAPTCHA_ENABLE", False):
        response = test_client.get("/system/auth/captcha/get")
        assert response.status_code == 200
        assert response.json()["data"]["enable"] is False


def test_public_probe_does_not_expose_monitor_details(test_client):
    response = test_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_docs_referer_alone_cannot_skip_captcha(test_client):
    """普通请求伪造文档来源仍需验证码，超管文档访问会话才可免验。"""
    with patch("app.modules.system.auth.service.settings.CAPTCHA_ENABLE", True):
        response = test_client.post("/system/auth/login", data={"username": "admin", "password": "admin123"}, headers={"Referer": "http://testserver/docs"})
        assert response.status_code != 200
        assert "验证码" in response.json()["msg"]


def test_authenticated_docs_session_can_authorize(test_client, auth_headers):
    assert test_client.post(PREFIX + "/docs-session", headers=auth_headers).status_code == 200
    with patch("app.modules.system.auth.service.settings.CAPTCHA_ENABLE", True):
        response = test_client.post("/system/auth/login", data={"username": "admin", "password": "admin123"}, headers={"Referer": "http://testserver/docs"})
        assert response.status_code == 200
        assert "access_token" in response.json()

"""服务端发布界面配置及超管策略，普通用户只接收裁剪后的视图。"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.modules.system.params.model import ParamsModel

from .crud import ProductConfigCRUD
from .schema import FeatureRule, ProductConfig

DEMO_PATHS = ("/fastlink/pricing", "/fastlink/changelog", "/fastlink/tutorial", "/fastlink/fachat", "/dashboard/analysis", "/dashboard/workplace")


def path_matches(path: str, prefix: str) -> bool:
    """匹配完整路径段，不将 /ai-example 误认为 /ai。"""
    return path == prefix.rstrip("/") or path.startswith(prefix.rstrip("/") + "/")


class ProductConfigService:
    """配置从数据库读取，跨请求及时生效，不依赖过期浏览器缓存。"""

    def __init__(self, db: AsyncSession) -> None:
        """业务校验和存储写入分层，沿用当前请求事务。"""
        self.db = db
        self.crud = ProductConfigCRUD(db)

    async def row(self) -> ParamsModel | None:
        """历史参数键没有唯一约束，重复记录拒绝使用而非随机选取。"""
        return await self.crud.row()

    async def read(self) -> ProductConfig:
        """缺省采用已确认的首版值，损坏配置拒绝放行。"""
        row = await self.row()
        return self.decode(row)

    @staticmethod
    def decode(row: ParamsModel | None) -> ProductConfig:
        """普通读取和发布锁定读取共用验证，不使用旧事务快照判断版本。"""
        if row is None:
            return ProductConfig()
        if row.status != 0 or row.is_deleted:
            raise CustomException(msg="产品配置不可用", status_code=503)
        try:
            return ProductConfig.model_validate_json(row.config_value or "")
        except ValueError as error:
            raise CustomException(msg="产品配置无效，请超管修复", status_code=503) from error

    async def initialize(self) -> None:
        """启动时只插入缺失记录，不覆盖已发布配置。"""
        await self.crud.initialize(ProductConfig().model_dump_json())

    @staticmethod
    def require_superuser(auth: AuthSchema) -> None:
        """只认可实际超管标志，角色名称及通配权限不能代替。"""
        if not auth.user.id or not auth.user.is_superuser:
            raise CustomException(msg="仅超管可使用此功能", status_code=403)

    @staticmethod
    def available(rule: FeatureRule, auth: AuthSchema) -> bool:
        """停用功能对超管也关闭，专属功能从不下发普通用户。"""
        return bool(rule.enabled and auth.user.id and auth.user.is_superuser)

    async def require_path(self, path: str, auth: AuthSchema) -> None:
        """配置驱动接口保护，支持后续追加路径，不影响业务基础服务。"""
        for rule in (await self.read()).features:
            if any(path_matches(path, prefix) for prefix in rule.api_prefixes) and not self.available(rule, auth):
                raise CustomException(msg="无权限访问该功能", status_code=403)

    async def require_feature(self, key: str, auth: AuthSchema) -> None:
        """别名入口按功能标识校验，修改文档地址不能绕过停用策略。"""
        rule = next((rule for rule in (await self.read()).features if rule.key == key), None)
        if rule is None or not self.available(rule, auth):
            raise CustomException(msg="无权限访问该功能", status_code=403)

    async def profile(self, auth: AuthSchema) -> dict[str, Any]:
        """普通用户响应不含专属策略、字段和快速入口链接。"""
        config = await self.read()
        values = config.settings.model_dump()
        capabilities = {}
        for rule in config.features:
            if self.available(rule, auth):
                capabilities[rule.key] = True
            if not (auth.user.id and auth.user.is_superuser):
                for key in rule.setting_keys:
                    values.pop(key, None)
        result = {"revision": config.revision, "settings": values, "capabilities": capabilities}
        if capabilities.get("quick_entry"):
            result["quick_links"] = [link.model_dump() for link in config.quick_links]
        return result

    async def publish(self, auth: AuthSchema, data: ProductConfig) -> ProductConfig:
        """版本比较更新避免覆盖其他超管发布，失败保持原配置。"""
        self.require_superuser(auth)
        await self.initialize()
        row = await self.crud.row(for_update=True)
        current = self.decode(row)
        if data.revision != current.revision:
            raise CustomException(msg="配置已更新，请重新加载后发布", status_code=409)
        data = data.model_copy(update={"revision": current.revision + 1})
        await self.crud.compare_and_swap(row, data.model_dump_json())
        return data

    async def filter_menus(self, menus: list[Any], auth: AuthSchema) -> list[Any]:
        """父项被过滤时连同子项一起过滤，防止相对路径子项重新出现。"""
        config = await self.read()
        blocked = set()
        for index, menu in enumerate(menus):
            path = menu.route_path or ""
            denied = any(path_matches(path, prefix) for prefix in DEMO_PATHS)
            denied |= (menu.component_path or "").startswith(("fastlink/pricing/", "fastlink/tutorial/", "fastlink/fachat/", "fastlink/changelog/", "dashboard/analysis/", "dashboard/workplace/", "module_system/auth/login/LegacyLogin"))
            for rule in config.features:
                matches = any(path_matches(path, prefix) for prefix in rule.menu_prefixes)
                matches |= any((menu.permission or "").startswith(prefix) for prefix in rule.permission_prefixes)
                matches |= any((menu.component_path or "").startswith(prefix) for prefix in rule.component_prefixes)
                link = getattr(menu, "link", "") or ""
                matches |= rule.key == "api_docs" and any(prefix in link for prefix in ("/docs", "/redoc", "/openapi.json"))
                matches |= rule.key == "api_docs" and (menu.component_path or "").startswith("module_swagger/")
                if matches and not self.available(rule, auth):
                    denied = True
                if matches:
                    menu = menu.model_copy(update={"feature_key": rule.key})
                    menus[index] = menu
                if matches and rule.key == "api_docs" and self.available(rule, auth):
                    menu = menu.model_copy(update={"type": 2, "component_path": "module_system/api_docs/index", "route_name": "Docs", "link": None, "is_iframe": False})
                    menus[index] = menu
            if denied:
                blocked.add(menu.id)
        changed = True
        while changed:
            before = len(blocked)
            blocked.update(menu.id for menu in menus if menu.parent_id in blocked)
            changed = before != len(blocked)
        visible = [menu for menu in menus if menu.id not in blocked]
        while True:
            parents = {menu.parent_id for menu in visible}
            reduced = [menu for menu in visible if menu.type != 1 or menu.id in parents]
            if len(reduced) == len(visible):
                return visible
            visible = reduced

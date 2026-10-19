"""智仓云默认界面与可扩展超管功能策略，运行状态不参与发布。"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, ValidationInfo, field_validator, model_validator

from app.config.setting import settings


class InterfaceSettings(BaseModel):
    """只接受可发布的界面字段，不接收令牌、刷新和弹窗状态。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    menuType: Literal["left", "top", "top-left", "dual-menu"] = "left"
    menuOpenWidth: int = Field(default=220, ge=180, le=400)
    menuOpen: bool = True
    dualMenuShowText: bool = False
    systemThemeType: Literal["light", "dark", "auto"] = "light"
    systemThemeMode: Literal["light", "dark", "auto"] = "light"
    menuThemeType: Literal["light", "dark", "design"] = "light"
    systemThemeColor: str = Field(default="#5D87FF", pattern=r"^#[0-9a-fA-F]{6}$")
    showMenuButton: bool = True
    showFastEnter: bool = True
    showRefreshButton: bool = True
    showCrumbs: bool = True
    showWorkTab: bool = True
    showLanguage: bool = False
    showNprogress: bool = True
    showSettingGuide: bool = False
    showFestivalText: bool = False
    watermarkVisible: bool = True
    showAppLogo: bool = True
    showGuide: bool = False
    grayMode: bool = False
    userEnableAi: bool = False
    autoClose: bool = False
    uniqueOpened: bool = True
    colorWeak: bool = False
    boxBorderMode: bool = False
    pageTransition: Literal["slide-left", "fade", "fade-slide", "fade-bottom", "fade-scale", "zoom-fade", "zoom-out", "none"] = "slide-left"
    tabStyle: Literal["tab-google", "tab-card", "tab-default"] = "tab-google"
    customRadius: str = Field(default="0.75", pattern=r"^(0(?:\.\d{1,2})?|1(?:\.0{1,2})?)$")
    containerWidth: Literal["100%", "1200px"] = "100%"
    showMenuSearch: bool = True
    showFullscreen: bool = True
    showSizeSelect: bool = True
    showNotification: bool = True


class FeatureRule(BaseModel):
    """策略可追加 API、菜单、权限及配置字段，不依赖前端角色名单。"""

    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,49}$")
    label: str = Field(min_length=1, max_length=60)
    enabled: bool = True
    access_policy: Literal["superuser_only"] = "superuser_only"
    built_in: bool = False
    api_prefixes: list[str] = Field(default_factory=list, max_length=20)
    menu_prefixes: list[str] = Field(default_factory=list, max_length=20)
    permission_prefixes: list[str] = Field(default_factory=list, max_length=20)
    component_prefixes: list[str] = Field(default_factory=list, max_length=20)
    setting_keys: list[str] = Field(default_factory=list, max_length=40)

    @field_validator("api_prefixes", "menu_prefixes")
    @classmethod
    def safe_paths(cls, values: list[str], info: ValidationInfo) -> list[str]:
        """拒绝根路径、查询串、空白及通配符，只做路径段边界匹配。"""
        values = [value.removeprefix(settings.ROOT_PATH).rstrip("/") if info.field_name == "api_prefixes" else value.rstrip("/") for value in values]
        for value in values:
            if not value.startswith("/") or value == "/" or len(value) > 200 or any(char in value for char in "?*#\\ ") or ".." in value:
                raise ValueError("路径前缀无效")
            if info.field_name == "api_prefixes" and any(core == value or core.startswith(value + "/") for core in ("/system/product-config", "/system/auth", "/system/user/current", "/system/param/info")):
                raise ValueError("不能将认证、配置发布或基础初始化入口纳入停用策略")
        return list(dict.fromkeys(values))

    @field_validator("setting_keys")
    @classmethod
    def known_settings(cls, values: list[str]) -> list[str]:
        """专属字段必须来自已定义的界面契约，不能过滤认证状态。"""
        if any(value not in InterfaceSettings.model_fields for value in values):
            raise ValueError("专属配置字段不存在")
        return list(dict.fromkeys(values))

    @field_validator("permission_prefixes", "component_prefixes")
    @classmethod
    def safe_identifiers(cls, values: list[str]) -> list[str]:
        """限制业务标识前缀，禁止空字符串匹配全部菜单。"""
        if any(not value or len(value) > 100 or any(char.isspace() for char in value) or "*" in value for value in values):
            raise ValueError("标识前缀无效")
        return list(dict.fromkeys(values))


def default_features() -> list[FeatureRule]:
    """内置模块的最小保护边界，超管可以停用或扩展但不能删减。"""
    rules = [
        FeatureRule(key="settings", label="界面配置与发布"),
        FeatureRule(key="quick_entry", label="快速入口", setting_keys=["showFastEnter"]),
        FeatureRule(key="ai", label="AI管理与助手", api_prefixes=["/ai"], menu_prefixes=["/ai"], permission_prefixes=["module_ai:"], component_prefixes=["module_ai/"], setting_keys=["userEnableAi"]),
        FeatureRule(key="monitor", label="监控管理", api_prefixes=["/monitor"], menu_prefixes=["/system/operations", "/monitor"], permission_prefixes=["module_monitor:"], component_prefixes=["module_monitor/"]),
        FeatureRule(key="api_docs", label="接口管理", api_prefixes=["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"], menu_prefixes=["/system/docs", "/system/api-docs", "/api-docs"], component_prefixes=["module_system/docs", "module_system/redoc"]),
        FeatureRule(key="task", label="任务管理", api_prefixes=["/task"], menu_prefixes=["/system/tasks", "/task"], permission_prefixes=["module_task:"], component_prefixes=["module_task/"]),
        FeatureRule(key="generator", label="代码生成", api_prefixes=["/generator"], menu_prefixes=["/generator"], permission_prefixes=["module_generator:"], component_prefixes=["module_generator/"]),
    ]
    return [rule.model_copy(update={"built_in": True}) for rule in rules]


class QuickLink(BaseModel):
    """仅允许 HTTP(S) 链接，不支持脚本及浏览器特殊协议。"""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    link: str = Field(min_length=1, max_length=500, pattern=r"^https?://[^\s]+$")
    enabled: bool = True
    order: int = Field(default=1, ge=0, le=1000)

    @field_validator("link")
    @classmethod
    def http_url(cls, value: str) -> str:
        """按标准 URL 解析验证，不依赖前缀字符串猜测合法地址。"""
        TypeAdapter(HttpUrl).validate_python(value)
        return value


def default_links() -> list[QuickLink]:
    """原头像菜单的仓库链接转为超管快速入口数据。"""
    return [QuickLink(name="GitHub", link="https://github.com/fastapiadmin/FastapiAdmin", order=1), QuickLink(name="Gitee", link="https://gitee.com/fastapiadmin/FastapiAdmin", order=2)]


class ProductConfig(BaseModel):
    """带版本的完整发布内容，仅超管读取。"""

    model_config = ConfigDict(extra="forbid")
    revision: int = Field(default=0, ge=0)
    settings: InterfaceSettings = Field(default_factory=InterfaceSettings)
    features: list[FeatureRule] = Field(default_factory=default_features, min_length=7, max_length=40)
    quick_links: list[QuickLink] = Field(default_factory=default_links, max_length=30)

    @model_validator(mode="after")
    def protected_boundaries(self) -> Self:
        """保留内置保护前缀和配置字段，避免发布遗漏扩大普通用户权限。"""
        by_key = {rule.key: rule for rule in self.features}
        built_in_keys = {rule.key for rule in default_features()}
        for rule in self.features:
            rule.built_in = rule.key in built_in_keys
        if len(by_key) != len(self.features):
            raise ValueError("功能标识不得重复")
        for default in default_features():
            current = by_key.get(default.key)
            if current is None:
                raise ValueError("不能移除内置超管策略")
            if default.key == "settings" and not current.enabled:
                raise ValueError("不能停用配置发布入口")
            for field in ("api_prefixes", "menu_prefixes", "permission_prefixes", "component_prefixes", "setting_keys"):
                if not set(getattr(default, field)) <= set(getattr(current, field)):
                    raise ValueError("不能缩减内置超管保护范围")
        return self

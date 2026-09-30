from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import MappedBase
from app.core.database import async_db_session, async_engine
from app.modules.system.menu.model import MenuModel
from app.modules.system.role.model import RoleMenusModel, RoleModel
from app.utils.import_util import ImportUtil

ImportUtil.find_models(MappedBase)


@dataclass(frozen=True, slots=True)
class MenuGroupSpec:
    """系统管理菜单分组定义。"""

    name: str
    route_name: str
    route_path: str
    icon: str
    order: int
    redirect: str
    children: tuple[str, ...]
    legacy_ancestors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InventoryPageSpec:
    """尚未交付的进销存页面菜单定义。"""

    name: str
    route_name: str
    route_path: str
    component_path: str
    permission: str
    icon: str
    order: int
    delivered: bool = False
    buttons: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class InventoryCatalogSpec:
    """进销存一级业务目录及其规划页面。"""

    name: str
    route_name: str
    route_path: str
    icon: str
    order: int
    redirect: str
    pages: tuple[InventoryPageSpec, ...]


GROUP_SPECS: tuple[MenuGroupSpec, ...] = (
    MenuGroupSpec(
        name="账号与权限",
        route_name="SystemAccess",
        route_path="/system/access",
        icon="ri:admin-line",
        order=1,
        redirect="/system/user",
        children=("User", "Role", "Dept", "Position", "Menu"),
    ),
    MenuGroupSpec(
        name="系统配置",
        route_name="SystemConfig",
        route_path="/system/config",
        icon="ri:settings-3-line",
        order=2,
        redirect="/system/dict",
        children=("Dict", "Params", "Notice", "ModuleVersion"),
    ),
    MenuGroupSpec(
        name="日志审计",
        route_name="SystemAudit",
        route_path="/system/audit",
        icon="ri:file-search-line",
        order=3,
        redirect="/system/log",
        children=("Log", "MonitorOnline"),
        legacy_ancestors=("Monitor",),
    ),
    MenuGroupSpec(
        name="运维监控",
        route_name="SystemOperations",
        route_path="/system/operations",
        icon="ri:pulse-line",
        order=4,
        redirect="/monitor/server",
        children=("MonitorServer", "MonitorCache"),
        legacy_ancestors=("Monitor",),
    ),
    MenuGroupSpec(
        name="开发工具",
        route_name="SystemDevtools",
        route_path="/system/devtools",
        icon="ri:code-box-line",
        order=5,
        redirect="/swagger/docs",
        children=("Docs", "GenCode"),
        legacy_ancestors=("Swagger", "Generator"),
    ),
    MenuGroupSpec(
        name="任务中心",
        route_name="SystemTasks",
        route_path="/system/tasks",
        icon="ri:calendar-todo-line",
        order=6,
        redirect="/task/cronjob/job",
        children=("Job", "Node", "WorkflowNode", "WorkflowBrowse", "WorkflowTransfer", "WorkflowFlow"),
        legacy_ancestors=("Task", "Cronjob", "Storage"),
    ),
)

PAGE_SETTINGS: dict[str, tuple[str, int, str | None]] = {
    "User": ("/system/user", 1, None),
    "Role": ("/system/role", 2, None),
    "Dept": ("/system/dept", 3, None),
    "Position": ("/system/position", 4, None),
    "Menu": ("/system/menu", 5, None),
    "Dict": ("/system/dict", 1, None),
    "Params": ("/system/param", 2, None),
    "Notice": ("/system/notice", 3, None),
    "ModuleVersion": ("/system/version/list", 4, None),
    "Log": ("/system/log", 1, None),
    "MonitorOnline": ("/monitor/online", 2, None),
    "MonitorServer": ("/monitor/server", 1, None),
    "MonitorCache": ("/monitor/cache", 2, None),
    "Docs": ("/swagger/docs", 1, "接口文档"),
    "GenCode": ("/generator/gencode", 2, None),
    "Job": ("/task/cronjob/job", 1, None),
    "Node": ("/task/cronjob/node", 2, "任务节点"),
    "WorkflowNode": ("/task/storage/node", 3, "存储节点"),
    "WorkflowBrowse": ("/task/storage/browse", 4, None),
    "WorkflowTransfer": ("/task/storage/transfer", 5, None),
    "WorkflowFlow": ("/task/storage/flow", 6, "存储流程"),
    "ModuleTicket": ("/system/ticket", 7, None),
}

LEGACY_CATALOGS: tuple[str, ...] = ("Monitor", "Swagger", "Generator", "Task", "Cronjob", "Storage")

INVENTORY_CATALOG_SPECS: tuple[InventoryCatalogSpec, ...] = (
    InventoryCatalogSpec(
        name="基础档案",
        route_name="InventoryBasic",
        route_path="/inventory/basic",
        icon="ri:archive-stack-line",
        order=2,
        redirect="/inventory/basic/category",
        pages=(
            InventoryPageSpec(
                "商品分类",
                "InventoryGoodsCategory",
                "/inventory/basic/category",
                "module_inventory/basic/category/index",
                "module_inventory:category:query",
                "ri:price-tag-3-line",
                1,
                delivered=True,
                buttons=(("新增", "create"), ("编辑", "update"), ("删除", "delete"), ("状态变更", "patch"), ("详情", "detail")),
            ),
            InventoryPageSpec("商品管理", "InventoryGoods", "/inventory/basic/goods", "module_inventory/basic/goods/index", "module_inventory:goods:query", "ri:box-3-line", 2),
            InventoryPageSpec("客户管理", "InventoryCustomer", "/inventory/basic/customer", "module_inventory/basic/customer/index", "module_inventory:customer:query", "ri:user-star-line", 3),
            InventoryPageSpec("供应商管理", "InventorySupplier", "/inventory/basic/supplier", "module_inventory/basic/supplier/index", "module_inventory:supplier:query", "ri:store-2-line", 4),
            InventoryPageSpec("仓库管理", "InventoryWarehouse", "/inventory/basic/warehouse", "module_inventory/basic/warehouse/index", "module_inventory:warehouse:query", "ri:home-gear-line", 5),
        ),
    ),
    InventoryCatalogSpec(
        name="采购管理",
        route_name="InventoryPurchase",
        route_path="/inventory/purchase",
        icon="ri:shopping-bag-3-line",
        order=3,
        redirect="/inventory/purchase/in",
        pages=(
            InventoryPageSpec("采购入库", "InventoryPurchaseIn", "/inventory/purchase/in", "module_inventory/purchase/in/index", "module_inventory:purchase_in:query", "ri:inbox-archive-line", 1),
            InventoryPageSpec(
                "采购退货", "InventoryPurchaseReturn", "/inventory/purchase/return", "module_inventory/purchase/return/index", "module_inventory:purchase_return:query", "ri:arrow-go-back-line", 2
            ),
        ),
    ),
    InventoryCatalogSpec(
        name="销售管理",
        route_name="InventorySale",
        route_path="/inventory/sale",
        icon="ri:hand-coin-line",
        order=4,
        redirect="/inventory/sale/out",
        pages=(
            InventoryPageSpec("销售出库", "InventorySaleOut", "/inventory/sale/out", "module_inventory/sale/out/index", "module_inventory:sale_out:query", "ri:send-plane-line", 1),
            InventoryPageSpec("销售退货", "InventorySaleReturn", "/inventory/sale/return", "module_inventory/sale/return/index", "module_inventory:sale_return:query", "ri:arrow-go-back-line", 2),
        ),
    ),
    InventoryCatalogSpec(
        name="库存管理",
        route_name="InventoryStock",
        route_path="/inventory/stock",
        icon="ri:stack-line",
        order=5,
        redirect="/inventory/stock/balance",
        pages=(
            InventoryPageSpec(
                "当前库存", "InventoryStockBalance", "/inventory/stock/balance", "module_inventory/stock/balance/index", "module_inventory:stock_balance:query", "ri:archive-drawer-line", 1
            ),
            InventoryPageSpec("库存流水", "InventoryStockLog", "/inventory/stock/log", "module_inventory/stock/log/index", "module_inventory:stock_log:query", "ri:file-list-3-line", 2),
            InventoryPageSpec("期初库存", "InventoryStockOpening", "/inventory/stock/opening", "module_inventory/stock/opening/index", "module_inventory:stock_opening:query", "ri:database-2-line", 3),
            InventoryPageSpec("库存盘点", "InventoryStockCheck", "/inventory/stock/check", "module_inventory/stock/check/index", "module_inventory:stock_check:query", "ri:survey-line", 4),
        ),
    ),
    InventoryCatalogSpec(
        name="往来管理",
        route_name="InventoryFinance",
        route_path="/inventory/finance",
        icon="ri:bank-card-line",
        order=6,
        redirect="/inventory/finance/receivable",
        pages=(
            InventoryPageSpec(
                "应收账款", "InventoryReceivable", "/inventory/finance/receivable", "module_inventory/finance/receivable/index", "module_inventory:receivable:query", "ri:money-cny-circle-line", 1
            ),
            InventoryPageSpec("应付账款", "InventoryPayable", "/inventory/finance/payable", "module_inventory/finance/payable/index", "module_inventory:payable:query", "ri:secure-payment-line", 2),
        ),
    ),
    InventoryCatalogSpec(
        name="报表中心",
        route_name="InventoryReport",
        route_path="/inventory/report",
        icon="ri:bar-chart-grouped-line",
        order=7,
        redirect="/inventory/report/purchase",
        pages=(
            InventoryPageSpec(
                "采购报表", "InventoryPurchaseReport", "/inventory/report/purchase", "module_inventory/report/purchase/index", "module_inventory:purchase_report:query", "ri:file-chart-line", 1
            ),
            InventoryPageSpec("销售报表", "InventorySaleReport", "/inventory/report/sale", "module_inventory/report/sale/index", "module_inventory:sale_report:query", "ri:line-chart-line", 2),
            InventoryPageSpec("库存报表", "InventoryStockReport", "/inventory/report/stock", "module_inventory/report/stock/index", "module_inventory:stock_report:query", "ri:pie-chart-2-line", 3),
            InventoryPageSpec("毛利报表", "InventoryProfitReport", "/inventory/report/profit", "module_inventory/report/profit/index", "module_inventory:profit_report:query", "ri:funds-line", 4),
        ),
    ),
)


def _create_group(spec: MenuGroupSpec, system_id: int) -> MenuModel:
    """根据固定配置创建不绑定组件的系统菜单分组。"""
    return MenuModel(
        name=spec.name,
        type=1,
        icon=spec.icon,
        order=spec.order,
        permission=None,
        route_name=spec.route_name,
        route_path=spec.route_path,
        component_path=None,
        status=0,
        keep_alive=True,
        hidden=False,
        always_show=True,
        title=spec.name,
        params=None,
        affix=False,
        redirect=spec.redirect,
        description="进销存菜单结构迁移",
        link=None,
        is_iframe=False,
        is_hide_tab=False,
        active_path=None,
        show_badge=False,
        show_text_badge=None,
        scope="web",
        parent_id=system_id,
    )


def _create_inventory_catalog(spec: InventoryCatalogSpec) -> MenuModel:
    """创建已启用但不绑定页面组件的进销存一级目录。"""
    return MenuModel(
        name=spec.name,
        type=1,
        icon=spec.icon,
        order=spec.order,
        permission=None,
        route_name=spec.route_name,
        route_path=spec.route_path,
        component_path=None,
        status=0,
        keep_alive=True,
        hidden=False,
        always_show=True,
        title=spec.name,
        params=None,
        affix=False,
        redirect=spec.redirect,
        description="进销存业务菜单",
        link=None,
        is_iframe=False,
        is_hide_tab=False,
        active_path=None,
        show_badge=False,
        show_text_badge=None,
        scope="web",
        parent_id=None,
    )


def _create_inventory_page(spec: InventoryPageSpec, parent_id: int) -> MenuModel:
    """创建进销存页面菜单，已交付页面直接启用。"""
    return MenuModel(
        name=spec.name,
        type=2,
        icon=spec.icon,
        order=spec.order,
        permission=spec.permission,
        route_name=spec.route_name,
        route_path=spec.route_path,
        component_path=spec.component_path,
        status=0 if spec.delivered else 1,
        keep_alive=True,
        hidden=False,
        always_show=False,
        title=spec.name,
        params=None,
        affix=False,
        redirect=None,
        description="进销存已交付菜单" if spec.delivered else "进销存规划菜单，功能实现后启用",
        link=None,
        is_iframe=False,
        is_hide_tab=False,
        active_path=None,
        show_badge=False,
        show_text_badge=None,
        scope="web",
        parent_id=parent_id,
    )


def _create_inventory_button(name: str, permission: str, order: int, parent_id: int) -> MenuModel:
    """创建进销存页面按钮权限节点。"""
    return MenuModel(
        name=name,
        type=3,
        icon=None,
        order=order,
        permission=permission,
        route_name=None,
        route_path=None,
        component_path=None,
        status=0,
        keep_alive=True,
        hidden=False,
        always_show=False,
        title=name,
        params=None,
        affix=False,
        redirect=None,
        description="商品分类按钮权限",
        link=None,
        is_iframe=False,
        is_hide_tab=False,
        active_path=None,
        show_badge=False,
        show_text_badge=None,
        scope="web",
        parent_id=parent_id,
    )


async def _grant_delivered_inventory_menus(
    db: AsyncSession,
    menu_ids: set[int],
) -> None:
    """为默认管理员角色补齐已交付进销存菜单权限。"""
    roles = list((await db.scalars(select(RoleModel).where(RoleModel.code.in_(("SUPER_ADMIN", "ADMIN"))))).all())
    existing_pairs = set((await db.execute(select(RoleMenusModel.role_id, RoleMenusModel.menu_id))).all())
    for role in roles:
        for menu_id in menu_ids:
            pair = (role.id, menu_id)
            if pair not in existing_pairs:
                db.add(RoleMenusModel(role_id=role.id, menu_id=menu_id))
                existing_pairs.add(pair)


async def _grant_group_ancestors(
    db: AsyncSession,
    menus: dict[str, MenuModel],
    groups: dict[str, MenuModel],
    system: MenuModel,
) -> None:
    """为原有页面角色补充新分组和系统管理祖先授权。"""
    existing_pairs = set((await db.execute(select(RoleMenusModel.role_id, RoleMenusModel.menu_id))).all())

    for spec in GROUP_SPECS:
        source_names = (*spec.children, *spec.legacy_ancestors)
        source_ids = [menus[name].id for name in source_names]
        role_ids = {role_id for role_id, menu_id in existing_pairs if menu_id in source_ids}
        target_ids = (groups[spec.route_name].id, system.id)
        for role_id in role_ids:
            for menu_id in target_ids:
                pair = (role_id, menu_id)
                if pair not in existing_pairs:
                    db.add(RoleMenusModel(role_id=role_id, menu_id=menu_id))
                    existing_pairs.add(pair)


async def restructure_inventory_menu() -> bool:
    """将平台技术菜单幂等迁移到进销存系统管理菜单下。"""
    async with async_db_session() as db, db.begin():
        menu_rows = list((await db.scalars(select(MenuModel).where(MenuModel.is_deleted.is_(False)))).all())
        menus = {menu.route_name: menu for menu in menu_rows if menu.route_name}

        group_names = {spec.route_name for spec in GROUP_SPECS}
        if group_names.issubset(menus):
            return False

        required_names = {"System", "AI", "ModuleTicket", *PAGE_SETTINGS, *LEGACY_CATALOGS}
        missing_names = sorted(required_names - menus.keys())
        if missing_names:
            raise RuntimeError(f"菜单数据不完整，缺少路由节点：{', '.join(missing_names)}")

        system = menus["System"]
        system.order = 9
        system.redirect = "/system/user"
        menus["AI"].order = 8

        groups: dict[str, MenuModel] = {}
        for spec in GROUP_SPECS:
            group = _create_group(spec, system.id)
            db.add(group)
            groups[spec.route_name] = group
        await db.flush()

        for spec in GROUP_SPECS:
            group = groups[spec.route_name]
            for route_name in spec.children:
                page = menus[route_name]
                route_path, order, display_name = PAGE_SETTINGS[route_name]
                page.parent_id = group.id
                page.route_path = route_path
                page.order = order
                if display_name:
                    page.name = display_name
                    page.title = display_name

        ticket = menus["ModuleTicket"]
        ticket.parent_id = system.id
        ticket.route_path, ticket.order, _ = PAGE_SETTINGS["ModuleTicket"]

        await _grant_group_ancestors(db, menus, groups, system)

        for route_name in LEGACY_CATALOGS:
            catalog = menus[route_name]
            catalog.hidden = True
            catalog.status = 1
            catalog.is_deleted = True

    return True


async def initialize_inventory_business_menus() -> int:
    """幂等创建进销存目录、页面和已交付功能按钮权限。"""
    async with async_db_session() as db, db.begin():
        menu_rows = list((await db.scalars(select(MenuModel).where(MenuModel.is_deleted.is_(False)))).all())
        menus = {menu.route_name: menu for menu in menu_rows if menu.route_name}
        menus_by_permission = {menu.permission: menu for menu in menu_rows if menu.permission}
        created_count = 0
        delivered_menu_ids: set[int] = set()

        for catalog_spec in INVENTORY_CATALOG_SPECS:
            catalog = menus.get(catalog_spec.route_name)
            if catalog is None:
                catalog = _create_inventory_catalog(catalog_spec)
                db.add(catalog)
                await db.flush()
                menus[catalog_spec.route_name] = catalog
                created_count += 1

            for page_spec in catalog_spec.pages:
                page = menus.get(page_spec.route_name)
                if page is None:
                    page = _create_inventory_page(page_spec, catalog.id)
                    db.add(page)
                    await db.flush()
                    menus[page_spec.route_name] = page
                    created_count += 1
                elif page_spec.delivered:
                    page.status = 0
                    page.description = "进销存已交付菜单"

                if not page_spec.delivered:
                    continue
                delivered_menu_ids.update((catalog.id, page.id))
                permission_prefix = page_spec.permission.rsplit(":", maxsplit=1)[0]
                for order, (button_name, action) in enumerate(page_spec.buttons, start=1):
                    permission = f"{permission_prefix}:{action}"
                    button = menus_by_permission.get(permission)
                    if button is None:
                        button = _create_inventory_button(button_name, permission, order, page.id)
                        db.add(button)
                        await db.flush()
                        menus_by_permission[permission] = button
                        created_count += 1
                    delivered_menu_ids.add(button.id)

        await _grant_delivered_inventory_menus(db, delivered_menu_ids)

    return created_count


async def run_inventory_menu_upgrade() -> bool:
    """执行菜单迁移并关闭命令行进程持有的数据库连接池。"""
    try:
        return await restructure_inventory_menu()
    finally:
        await async_engine.dispose()


async def run_inventory_business_menu_setup() -> int:
    """初始化进销存规划菜单并关闭命令行数据库连接池。"""
    try:
        return await initialize_inventory_business_menus()
    finally:
        await async_engine.dispose()

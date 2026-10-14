import json
from typing import Any

from app.config.path_conf import SCRIPT_DIR

EXPECTED_CATALOGS = {
    "InventoryBasic": (2, "/inventory/basic", 5),
    "InventoryPurchase": (3, "/inventory/purchase", 2),
    "InventorySale": (4, "/inventory/sale", 2),
    "InventoryStock": (5, "/inventory/stock", 4),
    "InventoryFinance": (6, "/inventory/finance", 2),
    "InventoryReport": (7, "/inventory/report", 4),
}


def _load_menu_seed() -> list[dict[str, Any]]:
    """读取后端菜单种子数据。"""
    with (SCRIPT_DIR / "sys_menu.json").open(encoding="utf-8") as file:
        return json.load(file)


def test_inventory_catalog_contract() -> None:
    """固定进销存一级目录排序、路径和规划页面数量。"""
    menus = _load_menu_seed()
    by_name = {menu.get("route_name"): menu for menu in menus}

    for route_name, (order, route_path, page_count) in EXPECTED_CATALOGS.items():
        catalog = by_name[route_name]
        assert catalog["type"] == 1
        assert catalog["status"] == 0
        assert catalog["order"] == order
        assert catalog["route_path"] == route_path
        assert catalog["component_path"] is None
        assert len(catalog["children"]) == page_count


def test_only_delivered_inventory_pages_are_enabled() -> None:
    """完整交付及前端预览页面均可见，但描述明确区分交付范围。"""
    menus = _load_menu_seed()
    catalogs = [menu for menu in menus if menu.get("route_name") in EXPECTED_CATALOGS]
    pages = [page for catalog in catalogs for page in catalog["children"]]
    delivered_names = {"InventoryGoodsCategory", "InventoryGoods", "InventoryCustomer", "InventorySupplier", "InventoryWarehouse", "InventoryPurchaseIn", "InventoryPurchaseReturn", "InventorySaleOut", "InventorySaleReturn"}
    delivered_names.update({"InventoryStockBalance", "InventoryStockLog", "InventoryStockOpening", "InventoryStockCheck"})
    delivered_names.update({"InventoryReceivable", "InventoryPayable"})
    delivered_names.update({"InventoryPurchaseReport", "InventorySaleReport", "InventoryStockReport", "InventoryProfitReport"})

    assert len(pages) == 19
    assert len({page["route_name"] for page in pages}) == 19
    assert all(page["type"] == 2 for page in pages)
    delivered_pages = [page for page in pages if page["route_name"] in delivered_names]
    pending_pages = [page for page in pages if page["route_name"] not in delivered_names]

    assert {page["route_name"] for page in delivered_pages} == delivered_names
    assert all(page["status"] == 0 for page in delivered_pages)
    assert all(page["description"] == "进销存已交付菜单" for page in delivered_pages)
    assert pending_pages == []
    assert all(page["route_path"].startswith("/inventory/") for page in pages)
    assert all(page["component_path"].startswith("module_inventory/") for page in pages)
    assert all(page["permission"].endswith(":query") for page in pages)


def test_purchase_button_permissions() -> None:
    """采购页面包含完整、有序且唯一的单据操作权限。"""
    menus = _load_menu_seed()
    purchase = next(menu for menu in menus if menu.get("route_name") == "InventoryPurchase")
    actions = ["create", "update", "detail", "delete", "confirm", "void", "export"]
    for page in purchase["children"]:
        prefix = page["permission"].removesuffix(":query")
        assert page["status"] == 0
        assert [button["permission"] for button in page["children"]] == [f"{prefix}:{action}" for action in actions]
        assert [button["order"] for button in page["children"]] == list(range(1, 8))
        assert all(button["type"] == 3 and button["status"] == 0 for button in page["children"])


def test_report_readonly_menu_contract() -> None:
    """四类报表只提供查询与导出，不增加报表写入或独立详情权限。"""
    from app.scripts.inventory_menu import INVENTORY_CATALOG_SPECS, _create_inventory_page

    report = next(menu for menu in _load_menu_seed() if menu.get("route_name") == "InventoryReport")
    spec = next(catalog for catalog in INVENTORY_CATALOG_SPECS if catalog.route_name == "InventoryReport")
    for page, page_spec in zip(report["children"], spec.pages, strict=True):
        assert page["status"] == 0 and page_spec.delivered
        assert not page_spec.frontend_only
        assert page["component_path"] == page_spec.component_path
        assert page["route_name"] == page_spec.route_name
        assert page["description"] == _create_inventory_page(page_spec, 1).description
        assert [button["permission"] for button in page["children"]] == [page["permission"].removesuffix(":query") + ":export"]
        assert [action for _, action in page_spec.buttons] == ["export"]


def test_finance_menu_contract() -> None:
    """往来只读权限与种子、初始化脚本保持一致。"""
    from app.scripts.inventory_menu import INVENTORY_CATALOG_SPECS

    finance = next(menu for menu in _load_menu_seed() if menu.get("route_name") == "InventoryFinance")
    spec = next(catalog for catalog in INVENTORY_CATALOG_SPECS if catalog.route_name == "InventoryFinance")
    for page, page_spec in zip(finance["children"], spec.pages, strict=True):
        assert page["status"] == 0 and page_spec.delivered
        assert page["component_path"] == page_spec.component_path
        prefix = page["permission"].removesuffix(":query")
        assert [button["permission"] for button in page["children"]] == [prefix + ":detail", prefix + ":export"]
        assert [action for _, action in page_spec.buttons] == ["detail", "export"]


def test_stock_menu_contract() -> None:
    """库存只读与单据权限分别配置，种子与初始化脚本一致。"""
    from app.scripts.inventory_menu import INVENTORY_CATALOG_SPECS

    stock = next(menu for menu in _load_menu_seed() if menu.get("route_name") == "InventoryStock")
    spec = next(catalog for catalog in INVENTORY_CATALOG_SPECS if catalog.route_name == "InventoryStock")
    for index, (page, page_spec) in enumerate(zip(stock["children"], spec.pages, strict=True)):
        actions = ["detail", "export"] if index < 2 else ["create", "update", "detail", "delete", "confirm", "void", "export"]
        prefix = page["permission"].removesuffix(":query")
        assert page["status"] == 0 and page_spec.delivered
        assert page["component_path"] == page_spec.component_path
        assert page["route_name"] == page_spec.route_name
        assert [action for _, action in page_spec.buttons] == actions
        assert [button["permission"] for button in page["children"]] == [f"{prefix}:{action}" for action in actions]


def test_sale_button_permissions_and_script_contract() -> None:
    """销售种子与初始化脚本保持路由、组件和按钮权限一致。"""
    from app.scripts.inventory_menu import INVENTORY_CATALOG_SPECS

    sale = next(menu for menu in _load_menu_seed() if menu.get("route_name") == "InventorySale")
    spec = next(catalog for catalog in INVENTORY_CATALOG_SPECS if catalog.route_name == "InventorySale")
    actions = ["create", "update", "detail", "delete", "confirm", "void", "export"]
    assert len(sale["children"]) == len(spec.pages) == 2
    for page, page_spec in zip(sale["children"], spec.pages, strict=True):
        prefix = page["permission"].removesuffix(":query")
        assert page["status"] == 0 and page_spec.delivered
        assert page["route_name"] == page_spec.route_name
        assert page["route_path"] == page_spec.route_path
        assert page["component_path"] == page_spec.component_path
        assert page["permission"] == page_spec.permission
        assert [action for _, action in page_spec.buttons] == actions
        assert [button["permission"] for button in page["children"]] == [f"{prefix}:{action}" for action in actions]
        assert [button["order"] for button in page["children"]] == list(range(1, 8))
        assert all(button["type"] == 3 and button["status"] == 0 for button in page["children"])


def test_goods_category_button_permissions() -> None:
    """商品分类页面包含完整且唯一的按钮权限。"""
    menus = _load_menu_seed()
    basic = next(menu for menu in menus if menu.get("route_name") == "InventoryBasic")
    category = next(page for page in basic["children"] if page.get("route_name") == "InventoryGoodsCategory")

    permissions = {button["permission"] for button in category["children"]}
    assert permissions == {
        "module_inventory:category:create",
        "module_inventory:category:update",
        "module_inventory:category:delete",
        "module_inventory:category:patch",
        "module_inventory:category:detail",
    }
    assert all(button["type"] == 3 and button["status"] == 0 for button in category["children"])


def test_goods_button_permissions() -> None:
    """商品管理页面已启用并包含完整、有序且唯一的按钮权限。"""
    menus = _load_menu_seed()
    basic = next(menu for menu in menus if menu.get("route_name") == "InventoryBasic")
    goods = next(page for page in basic["children"] if page.get("route_name") == "InventoryGoods")

    assert goods["status"] == 0
    assert goods["order"] == 2
    assert goods["description"] == "进销存已交付菜单"

    permissions = {button["permission"] for button in goods["children"]}
    assert permissions == {
        "module_inventory:goods:create",
        "module_inventory:goods:update",
        "module_inventory:goods:delete",
        "module_inventory:goods:patch",
        "module_inventory:goods:detail",
        "module_inventory:goods:export",
    }
    assert len(goods["children"]) == len(permissions) == 6
    assert [button["order"] for button in goods["children"]] == [1, 2, 3, 4, 5, 6]
    assert all(button["type"] == 3 and button["status"] == 0 for button in goods["children"])

def test_customer_button_permissions() -> None:
    """客户管理页面已启用并包含完整、有序且唯一的按钮权限。"""
    menus = _load_menu_seed()
    basic = next(menu for menu in menus if menu.get("route_name") == "InventoryBasic")
    customer = next(page for page in basic["children"] if page.get("route_name") == "InventoryCustomer")

    assert customer["status"] == 0
    assert customer["order"] == 3
    assert customer["description"] == "进销存已交付菜单"

    permissions = {button["permission"] for button in customer["children"]}
    assert permissions == {
        "module_inventory:customer:create",
        "module_inventory:customer:update",
        "module_inventory:customer:delete",
        "module_inventory:customer:patch",
        "module_inventory:customer:detail",
        "module_inventory:customer:export",
    }
    assert len(customer["children"]) == len(permissions) == 6
    assert [button["order"] for button in customer["children"]] == [1, 2, 3, 4, 5, 6]
    assert all(button["type"] == 3 and button["status"] == 0 for button in customer["children"])


def test_supplier_button_permissions() -> None:
    """供应商管理页面已启用并包含完整、有序且唯一的按钮权限。"""
    menus = _load_menu_seed()
    basic = next(menu for menu in menus if menu.get("route_name") == "InventoryBasic")
    supplier = next(page for page in basic["children"] if page.get("route_name") == "InventorySupplier")

    assert supplier["status"] == 0
    assert supplier["order"] == 4
    assert supplier["description"] == "进销存已交付菜单"

    permissions = {button["permission"] for button in supplier["children"]}
    assert permissions == {
        "module_inventory:supplier:create",
        "module_inventory:supplier:update",
        "module_inventory:supplier:delete",
        "module_inventory:supplier:patch",
        "module_inventory:supplier:detail",
        "module_inventory:supplier:export",
    }
    assert len(supplier["children"]) == len(permissions) == 6
    assert [button["order"] for button in supplier["children"]] == [1, 2, 3, 4, 5, 6]
    assert all(button["type"] == 3 and button["status"] == 0 for button in supplier["children"])

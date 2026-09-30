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


def test_only_delivered_inventory_page_is_enabled() -> None:
    """仅已交付的商品分类页面启用，其余页面继续停用。"""
    menus = _load_menu_seed()
    catalogs = [menu for menu in menus if menu.get("route_name") in EXPECTED_CATALOGS]
    pages = [page for catalog in catalogs for page in catalog["children"]]

    assert len(pages) == 19
    assert len({page["route_name"] for page in pages}) == 19
    assert all(page["type"] == 2 for page in pages)
    category = next(page for page in pages if page["route_name"] == "InventoryGoodsCategory")
    pending_pages = [page for page in pages if page is not category]

    assert category["status"] == 0
    assert category["description"] == "进销存已交付菜单"
    assert all(page["status"] == 1 for page in pending_pages)
    assert all(page["route_path"].startswith("/inventory/") for page in pages)
    assert all(page["component_path"].startswith("module_inventory/") for page in pages)
    assert all(page["permission"].endswith(":query") for page in pages)


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

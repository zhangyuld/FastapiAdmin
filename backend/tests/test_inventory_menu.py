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
    """仅已交付的商品分类和商品管理页面启用。"""
    menus = _load_menu_seed()
    catalogs = [menu for menu in menus if menu.get("route_name") in EXPECTED_CATALOGS]
    pages = [page for catalog in catalogs for page in catalog["children"]]
    delivered_names = {"InventoryGoodsCategory", "InventoryGoods"}

    assert len(pages) == 19
    assert len({page["route_name"] for page in pages}) == 19
    assert all(page["type"] == 2 for page in pages)
    delivered_pages = [page for page in pages if page["route_name"] in delivered_names]
    pending_pages = [page for page in pages if page["route_name"] not in delivered_names]

    assert {page["route_name"] for page in delivered_pages} == delivered_names
    assert all(page["status"] == 0 for page in delivered_pages)
    assert all(page["description"] == "进销存已交付菜单" for page in delivered_pages)
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

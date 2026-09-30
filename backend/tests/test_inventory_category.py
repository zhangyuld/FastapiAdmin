from fastapi.testclient import TestClient


def _create_category(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str,
    parent_id: int | None = None,
) -> dict:
    """通过接口创建测试分类。"""
    response = client.post(
        "/inventory/basic/category/create",
        headers=headers,
        json={"name": name, "parent_id": parent_id, "sort": 1, "status": 0},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_goods_category_tree_crud_and_status_cascade(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """商品分类支持树形 CRUD、层级保护和状态级联。"""
    root = _create_category(test_client, auth_headers, name="测试分类根节点")
    child = _create_category(
        test_client,
        auth_headers,
        name="测试分类子节点",
        parent_id=root["id"],
    )

    duplicate = test_client.post(
        "/inventory/basic/category/create",
        headers=auth_headers,
        json={"name": child["name"], "parent_id": root["id"], "sort": 2, "status": 0},
    )
    assert duplicate.status_code == 409
    assert "同名分类" in duplicate.json()["msg"]

    circular = test_client.put(
        f"/inventory/basic/category/update/{root['id']}",
        headers=auth_headers,
        json={"name": root["name"], "parent_id": child["id"], "sort": 1, "status": 0},
    )
    assert circular.status_code == 400
    assert "子分类" in circular.json()["msg"]

    protected_delete = test_client.request(
        "DELETE",
        "/inventory/basic/category/delete",
        headers=auth_headers,
        json=[root["id"]],
    )
    assert protected_delete.status_code == 409
    assert "存在子分类" in protected_delete.json()["msg"]

    disable = test_client.patch(
        "/inventory/basic/category/status/batch",
        headers=auth_headers,
        json={"ids": [root["id"]], "status": 1},
    )
    assert disable.status_code == 200, disable.text
    child_detail = test_client.get(
        f"/inventory/basic/category/detail/{child['id']}",
        headers=auth_headers,
    )
    assert child_detail.json()["data"]["status"] == 1

    enable = test_client.patch(
        "/inventory/basic/category/status/batch",
        headers=auth_headers,
        json={"ids": [child["id"]], "status": 0},
    )
    assert enable.status_code == 200, enable.text
    root_detail = test_client.get(
        f"/inventory/basic/category/detail/{root['id']}",
        headers=auth_headers,
    )
    assert root_detail.json()["data"]["status"] == 0

    tree = test_client.get("/inventory/basic/category/tree", headers=auth_headers)
    assert tree.status_code == 200, tree.text
    root_node = next(item for item in tree.json()["data"] if item["id"] == root["id"])
    assert any(item["id"] == child["id"] for item in root_node["children"])

    delete_child = test_client.request(
        "DELETE",
        "/inventory/basic/category/delete",
        headers=auth_headers,
        json=[child["id"]],
    )
    assert delete_child.status_code == 200, delete_child.text
    delete_root = test_client.request(
        "DELETE",
        "/inventory/basic/category/delete",
        headers=auth_headers,
        json=[root["id"]],
    )
    assert delete_root.status_code == 200, delete_root.text

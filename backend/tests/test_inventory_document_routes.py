"""采购、销售接口地址与业务目录命名保持一致。"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "prefix",
    ["/inventory/purchase/inbound", "/inventory/purchase/return_order", "/inventory/sale/out", "/inventory/sale/return_order"],
)
def test_document_routes_use_semantic_prefixes(test_client: TestClient, prefix: str) -> None:
    """实际应用注册所有 GET 查询及 POST 写入、导出，不引入其他方法。"""
    paths = test_client.app.openapi()["paths"]
    endpoints = {
        "/list": "get",
        "/detail/{id}": "get",
        "/create": "post",
        "/update/{id}": "post",
        "/delete": "post",
        "/confirm/{id}": "post",
        "/void/{id}": "post",
        "/export": "post",
    }
    for suffix, method in endpoints.items():
        assert set(paths[prefix + suffix]) == {method}


@pytest.mark.parametrize("prefix", ["/inventory/purchase/in", "/inventory/purchase/return", "/inventory/sale/return"])
def test_keyword_api_prefixes_are_not_registered(test_client: TestClient, prefix: str) -> None:
    """旧地址不提供兼容别名，避免文档与前端继续使用过时接口。"""
    paths = test_client.app.openapi()["paths"]
    assert not any(path == prefix or path.startswith(prefix + "/") for path in paths)


@pytest.mark.parametrize("prefix", ["/inventory/purchase/inbound", "/inventory/sale/out"])
def test_source_document_queries_follow_semantic_prefixes(test_client: TestClient, prefix: str) -> None:
    """可退额度及关联退货分页随原单接口前缀同步调整。"""
    paths = test_client.app.openapi()["paths"]
    for suffix in ("/returnable/{id}", "/returns/{id}"):
        assert set(paths[prefix + suffix]) == {"get"}

import json
import re
from datetime import date, datetime
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace
from typing import Annotated, Any

import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.utils.common_util import search_to_dict

# in 为 Python 关键字，通过模块路径加载，业务模块内部仍可使用相对导入。
schema = import_module("app.modules.inventory.purchase.in.schema")


@pytest.fixture
def create_body() -> dict[str, Any]:
    """构造与采购入库前端一致的草稿入参。"""
    return {
        "supplier_id": 1,
        "warehouse_id": 2,
        "business_date": "2026-10-12",
        "remark": "  测试采购  ",
        "items": [{"goods_id": 3, "quantity": "2.000", "unit_price": "12.3456"}],
    }


def test_create_parses_decimal_and_date(create_body: dict[str, Any]) -> None:
    """入参在 Python 中使用 Decimal 和 date，JSON 输出固定精度。"""
    data = schema.PurchaseInCreateSchema.model_validate(create_body)
    assert data.business_date == date(2026, 10, 12)
    assert data.remark == "测试采购"
    assert data.items[0].quantity == Decimal("2.000")
    assert data.items[0].unit_price == Decimal("12.3456")
    assert isinstance(data.model_dump()["items"][0]["quantity"], Decimal)
    dumped = data.model_dump(mode="json")
    assert dumped["items"][0]["quantity"] == "2.000"
    assert dumped["items"][0]["unit_price"] == "12.3456"


@pytest.mark.parametrize("remark", [None, "", "  "])
def test_empty_remark_becomes_none(create_body: dict[str, Any], remark: str | None) -> None:
    """空备注统一归一为空值。"""
    create_body["remark"] = remark
    assert schema.PurchaseInCreateSchema.model_validate(create_body).remark is None


@pytest.mark.parametrize("field", ["order_no", "status", "total_amount", "created_id", "version"])
def test_create_rejects_server_fields(create_body: dict[str, Any], field: str) -> None:
    """新建草稿拒绝客户端指定后端管理的字段。"""
    create_body[field] = 1
    with pytest.raises(ValidationError):
        schema.PurchaseInCreateSchema.model_validate(create_body)


@pytest.mark.parametrize("field", ["line_no", "goods_name", "line_amount", "id"])
def test_items_reject_snapshot_fields(create_body: dict[str, Any], field: str) -> None:
    """明细不能伪造行号、快照或金额。"""
    create_body["items"][0][field] = 1
    with pytest.raises(ValidationError):
        schema.PurchaseInCreateSchema.model_validate(create_body)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("quantity", "0"),
        ("quantity", "-1"),
        ("quantity", "0.0001"),
        ("quantity", "1000000000000000"),
        ("quantity", "NaN"),
        ("quantity", "Infinity"),
        ("unit_price", "-1"),
        ("unit_price", "1.00001"),
        ("unit_price", "100000000000000"),
        ("unit_price", "NaN"),
        ("unit_price", "Infinity"),
        ("goods_id", 0),
        ("goods_id", True),
    ],
)
def test_invalid_items_rejected(create_body: dict[str, Any], field: str, value: Any) -> None:
    """拒绝超精度、超数据库范围、非有限数值及非法商品ID。"""
    create_body["items"][0][field] = value
    with pytest.raises(ValidationError):
        schema.PurchaseInCreateSchema.model_validate(create_body)


def test_zero_price_and_numeric_input_allowed(create_body: dict[str, Any]) -> None:
    """允许零价采购和普通 JSON 数字输入。"""
    create_body["items"][0].update(quantity=1.25, unit_price=0)
    result = schema.PurchaseInCreateSchema.model_validate(create_body).model_dump(mode="json")
    assert result["items"][0]["quantity"] == "1.250"
    assert result["items"][0]["unit_price"] == "0.0000"


def test_empty_and_duplicate_items_rejected(create_body: dict[str, Any]) -> None:
    """草稿必须有明细且商品不能重复。"""
    create_body["items"] *= 2
    with pytest.raises(ValidationError, match="重复商品"):
        schema.PurchaseInCreateSchema.model_validate(create_body)
    create_body["items"] = []
    with pytest.raises(ValidationError):
        schema.PurchaseInCreateSchema.model_validate(create_body)


@pytest.mark.parametrize("version", [None, -1, True, "0"])
def test_update_requires_integer_version(create_body: dict[str, Any], version: Any) -> None:
    """更新必须携带真实的非负整数版本。"""
    if version is not None:
        create_body["version"] = version
    with pytest.raises(ValidationError):
        schema.PurchaseInUpdateSchema.model_validate(create_body)


def test_update_accepts_initial_version(create_body: dict[str, Any]) -> None:
    """零为有效初始版本，更新仍提交完整草稿。"""
    create_body["version"] = 0
    assert schema.PurchaseInUpdateSchema.model_validate(create_body).version == 0


@pytest.mark.parametrize("dates", [["2026-10-12"], [], ["2026-10-13", "2026-10-12"], ["invalid", "2026-10-12"]])
def test_query_rejects_invalid_date_ranges(dates: list[str]) -> None:
    """日期范围必须有两个有效且有序的日期。"""
    with pytest.raises(ValidationError):
        schema.PurchaseInQueryParam(business_date=dates)


def test_query_converts_to_database_conditions() -> None:
    """业务日期显式生成 between，并复用框架审计条件。"""
    query = schema.PurchaseInQueryParam(order_no="  PI001  ", supplier_id=1, business_date=["2026-10-01", "2026-10-12"], status=0, created_id=2)
    conditions = search_to_dict(query)
    assert conditions["order_no"] == ("like", "PI001")
    assert conditions["supplier_id"] == ("eq", 1)
    assert conditions["status"] == ("eq", 0)
    assert conditions["created_id"] == ("eq", 2)
    assert conditions["business_date"] == ("between", [date(2026, 10, 1), date(2026, 10, 12)])
    assert "order_no" not in search_to_dict(schema.PurchaseInQueryParam(order_no="  "))


def test_query_accepts_http_strings_and_date_arrays() -> None:
    """GET 查询模型接收字符串状态、关联ID和重复日期参数。"""
    app = FastAPI()

    @app.get("/list")
    def list_endpoint(query: Annotated[schema.PurchaseInQueryParam, Query()]) -> dict[str, Any]:
        """返回校验后的查询条件，验证真实 HTTP 绑定。"""
        return query.model_dump(mode="json")

    with TestClient(app) as client:
        response = client.get("/list", params=[("status", "0"), ("supplier_id", "1"), ("business_date", "2026-10-01"), ("business_date", "2026-10-12")])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == 0
    assert response.json()["business_date"] == ["2026-10-01", "2026-10-12"]


def test_delete_normalizes_json_keys_and_ids() -> None:
    """JSON 版本映射键转换为整数，待删除ID顺序去重。"""
    data = schema.PurchaseInDeleteSchema.model_validate_json('{"ids":[3,3,4],"versions":{"3":0,"4":2}}')
    assert data.ids == [3, 4]
    assert data.versions == {3: 0, 4: 2}


@pytest.mark.parametrize(
    "body",
    [
        {"ids": [], "versions": {}},
        {"ids": [0], "versions": {"0": 0}},
        {"ids": [3], "versions": {}},
        {"ids": [3], "versions": {"4": 0}},
        {"ids": [3], "versions": {"3": 0, "4": 1}},
        {"ids": [3], "versions": {"3": -1}},
        {"ids": [3], "versions": {"3": True}},
    ],
)
def test_delete_rejects_unmatched_versions(body: dict[str, Any]) -> None:
    """删除版本不可缺失、额外提供或为非法值。"""
    with pytest.raises(ValidationError):
        schema.PurchaseInDeleteSchema.model_validate(body)


def test_confirm_and_void_validation() -> None:
    """确认必须带版本，作废还需有效原因。"""
    assert schema.PurchaseInConfirmSchema(version=0).version == 0
    assert schema.PurchaseInVoidSchema(version=1, void_reason="  录入错误  ").void_reason == "录入错误"
    for body in [{"version": -1}, {"version": 1, "void_reason": "  "}, {"version": 1, "void_reason": "错" * 501}]:
        with pytest.raises(ValidationError):
            schema.PurchaseInVoidSchema.model_validate(body)


@pytest.fixture
def document_body() -> dict[str, Any]:
    """构造包含完整商品快照的详情响应。"""
    return {
        "id": 1,
        "order_no": "PI001",
        "supplier_id": 1,
        "supplier_name": "供应商",
        "warehouse_id": 2,
        "warehouse_name": "仓库",
        "business_date": date(2026, 10, 12),
        "total_amount": Decimal("1.20"),
        "status": 1,
        "version": 1,
        "confirmed_time": datetime(2026, 10, 12, 10, 30),
        "return_summary": {"return_status": "none", "confirmed_count": 0, "returned_amount": "0.00"},
        "items": [
            {
                "id": 3,
                "line_no": 1,
                "goods_id": 4,
                "goods_code": "G001",
                "goods_name": "商品",
                "unit": "件",
                "quantity": Decimal("2"),
                "unit_price": Decimal("0.6"),
                "line_amount": Decimal("1.2"),
                "returned_quantity": Decimal("0"),
                "returnable_quantity": Decimal("2"),
            }
        ],
    }


def test_output_reads_attributes_and_formats_decimals(document_body: dict[str, Any]) -> None:
    """响应可读取 ORM 风格属性并按 JSON 格式序列化金额与时间。"""
    document_body["items"] = [SimpleNamespace(**item) for item in document_body["items"]]
    data = schema.PurchaseInDetailOutSchema.model_validate(SimpleNamespace(**document_body))
    dumped = json.loads(data.model_dump_json())
    assert dumped["total_amount"] == "1.20"
    assert dumped["business_date"] == "2026-10-12"
    assert dumped["confirmed_time"] == "2026-10-12 10:30:00"
    assert dumped["items"][0]["quantity"] == "2.000"
    assert dumped["items"][0]["unit_price"] == "0.6000"
    assert dumped["items"][0]["line_amount"] == "1.20"
    assert dumped["items"][0]["returned_quantity"] == "0.000"
    assert dumped["return_summary"]["returned_amount"] == "0.00"


def test_list_omits_items_but_detail_requires_items(document_body: dict[str, Any]) -> None:
    """列表不返回明细，详情禁止默默丢失明细。"""
    assert "items" not in schema.PurchaseInOutSchema.model_validate(document_body).model_dump()
    document_body.pop("items")
    with pytest.raises(ValidationError):
        schema.PurchaseInDetailOutSchema.model_validate(document_body)


def test_returnable_requires_each_line_quantity(document_body: dict[str, Any]) -> None:
    """来源明细必须包含可退数量，允许已经全部退完的零数量。"""
    document_body["items"][0].pop("returnable_quantity")
    with pytest.raises(ValidationError):
        schema.PurchaseInReturnableOutSchema.model_validate(document_body)
    document_body["items"][0]["returnable_quantity"] = "0"
    result = schema.PurchaseInReturnableOutSchema.model_validate(document_body).model_dump(mode="json")
    assert result["items"][0]["returnable_quantity"] == "0.000"
    with pytest.raises(ValidationError):
        schema.PurchaseInReturnableQueryParam(exclude_return_id=0)


def test_export_keeps_order_and_filename_defaults() -> None:
    """导出保留字段顺序，并按约定生成或清理文件名。"""
    data = schema.PurchaseInExportSchema(fields=["total_amount", "order_no", "total_amount"], filename="  采购记录.XLSX  ", format="csv")
    assert data.fields == ["total_amount", "order_no"]
    assert data.get_download_filename() == "采购记录.csv"
    assert re.fullmatch(r"采购入库列表_\d{8}_\d{6}\.xlsx", schema.PurchaseInExportSchema(filename=" ").get_download_filename())


@pytest.mark.parametrize(
    "body",
    [
        {"fields": []},
        {"fields": ["password"]},
        {"format": "pdf"},
        {"filename": "../采购"},
        {"filename": "采购\\记录"},
        {"filename": ".xlsx"},
        {"filename": "采购\n记录"},
        {"sheet_name": "采购[入库]"},
        {"sheet_name": "采购\n入库"},
        {"sheet_name": "单" * 32},
    ],
)
def test_export_rejects_invalid_options(body: dict[str, Any]) -> None:
    """导出拒绝非法字段、格式、路径及工作表名称。"""
    with pytest.raises(ValidationError):
        schema.PurchaseInExportSchema.model_validate(body)

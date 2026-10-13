from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from app.modules.inventory.sale.return_order import schema as schema


@pytest.fixture
def valid_return() -> dict[str, Any]:
    """提供原单退货最小合法请求。"""
    return {
        "customer_id": 1,
        "warehouse_id": 1,
        "source_sale_out_id": 1,
        "business_date": "2026-10-12",
        "return_reason": "  质量问题  ",
        "remark": "  ",
        "items": [{"goods_id": 1, "source_sale_out_item_id": 2, "quantity": "0.500", "unit_price": "2.0000"}],
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_sale_out_id", None),
        ("source_sale_out_id", 0),
        ("customer_id", True),
        ("warehouse_id", -1),
        ("return_reason", " "),
        ("return_reason", "x" * 501),
        ("items", []),
        ("status", 1),
        ("return_amount", "1"),
        ("discount_amount", "1"),
        ("original_amount", "1"),
        ("receivable_amount", "1"),
        ("business_date", "invalid"),
    ],
)
def test_return_schema_rejects_invalid_main(valid_return: dict[str, Any], field: str, value: Any) -> None:
    """来源、原因、精度及服务端字段不可绕过序列化校验。"""
    valid_return[field] = value
    with pytest.raises(ValidationError):
        schema.SaleReturnCreateSchema.model_validate(valid_return)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_sale_out_item_id", None),
        ("source_sale_out_item_id", True),
        ("quantity", "0"),
        ("quantity", "1.0001"),
        ("quantity", "NaN"),
        ("unit_price", "-1"),
        ("unit_price", "1.00001"),
        ("unit_cost", "2"),
        ("cost_amount", "2"),
    ],
)
def test_return_schema_rejects_invalid_item(valid_return: dict[str, Any], field: str, value: Any) -> None:
    """来源行必填，金额成本不能由客户端注入。"""
    valid_return["items"][0][field] = value
    with pytest.raises(ValidationError):
        schema.SaleReturnCreateSchema.model_validate(valid_return)


def test_return_schema_normalization_and_duplicates(valid_return: dict[str, Any]) -> None:
    """字符串精度固定，空白规范化，重复来源行被拒绝。"""
    result = schema.SaleReturnCreateSchema.model_validate(valid_return)
    assert result.return_reason == "质量问题" and result.remark is None
    assert result.model_dump(mode="json")["items"][0]["quantity"] == "0.500"
    valid_return["items"].append(deepcopy(valid_return["items"][0]))
    with pytest.raises(ValidationError):
        schema.SaleReturnCreateSchema.model_validate(valid_return)
    with pytest.raises(ValidationError):
        schema.SaleReturnUpdateSchema.model_validate({**valid_return, "version": True})


def test_return_export_validation() -> None:
    """退货独立字段白名单、字段顺序及默认文件名前缀正确。"""
    output = schema.SaleReturnExportSchema(fields=["source_order_no", "return_reason", "source_order_no"], filename="退货明细.xlsx")
    assert output.fields == ["source_order_no", "return_reason"]
    assert output.get_download_filename() == "退货明细.xlsx"
    assert schema.SaleReturnExportSchema(filename="").get_download_filename().startswith("销售退货列表_")
    assert schema.SaleReturnExportSchema(sheet_name=" ").sheet_name == "销售退货"
    for fields in [[], ["unit_cost"], ["unknown"]]:
        with pytest.raises(ValidationError):
            schema.SaleReturnExportSchema(fields=fields)
    with pytest.raises(ValidationError):
        schema.SaleReturnExportSchema(filename="../escape")
    with pytest.raises(ValidationError):
        schema.SaleReturnQueryParam(business_date=["2026-10-13", "2026-10-12"])

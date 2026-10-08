from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.base_schema import BaseQueryParam, BaseSchema, UserByQueryParam, UserBySchema


class GoodsBaseSchema(BaseModel):
    """商品基础字段。"""

    goods_name: str = Field(..., max_length=200, description="商品名称")
    goods_code: str = Field(..., max_length=64, description="商品编码")
    category_id: int = Field(..., ge=1, description="分类ID")
    spec: str | None = Field(default=None, max_length=200, description="规格型号")
    unit: str = Field(..., max_length=32, description="基本单位")
    reference_cost_price: Decimal = Field(..., ge=0, max_digits=18, decimal_places=4, description="参考进价")
    sale_price: Decimal = Field(..., ge=0, max_digits=18, decimal_places=4, description="默认销售价")
    stock_min: Decimal = Field(..., ge=0, max_digits=18, decimal_places=3, description="最低库存")
    stock_max: Decimal = Field(..., ge=0, max_digits=18, decimal_places=3, description="最高库存，0表示不限制")
    remark: str | None = Field(default=None, max_length=500, description="备注")
    status: int = Field(..., ge=0, le=1, description="状态(0:启用 1:停用)")

    @field_validator("goods_name", "goods_code", "unit")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """清理必填文本并拒绝纯空白内容。"""
        result = value.strip()
        if not result:
            raise ValueError("商品名称、商品编码和基本单位不能为空")
        return result

    @field_validator("spec", "remark")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """清理可选文本，空白内容统一存储为空值。"""
        if value is None:
            return None
        return value.strip() or None


class GoodsCreateSchema(GoodsBaseSchema):
    """商品创建参数。"""

    @model_validator(mode="after")
    def validate_price_and_stock(self) -> Self:
        """校验售价及库存上下限的跨字段约束。"""
        if self.sale_price < self.reference_cost_price:
            raise ValueError("默认销售价不能低于参考进价")
        if self.stock_max != 0 and self.stock_max < self.stock_min:
            raise ValueError("最高库存不能低于最低库存")
        return self


class GoodsUpdateSchema(GoodsCreateSchema):
    """商品修改参数。"""

class GoodsDeleteSchema(BaseModel):
    """商品批量删除参数。"""

    ids: list[int] = Field(..., min_length=1, description="商品ID列表")

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, value: list[int]) -> list[int]:
        """校验商品ID为正整数并按传入顺序去重。"""
        if any(item < 1 for item in value):
            raise ValueError("商品ID必须为正整数")
        return list(dict.fromkeys(value))


class GoodsOutSchema(GoodsBaseSchema, BaseSchema, UserBySchema):
    """商品详情响应。"""

    model_config = ConfigDict(from_attributes=True)

    category_name: str | None = Field(default=None, description="商品分类名称")


class GoodsQueryParam(BaseQueryParam, UserByQueryParam):
    """商品查询参数。"""

    goods_name: str | None = Field(default=None, max_length=200, description="商品名称", json_schema_extra={"q": "like"})
    goods_code: str | None = Field(default=None, max_length=64, description="商品编码", json_schema_extra={"q": "like"})
    category_id: int | None = Field(default=None, ge=1, description="分类ID", json_schema_extra={"q": "eq"})
    status: int | None = Field(default=None, ge=0, le=1, description="状态(0:启用 1:停用)", json_schema_extra={"q": "eq"})


GoodsExportField = Literal[
    "goods_code",
    "goods_name",
    "category_name",
    "spec",
    "unit",
    "reference_cost_price",
    "sale_price",
    "stock_min",
    "stock_max",
    "status",
    "remark",
    "created_time",
    "updated_time",
]

DEFAULT_GOODS_EXPORT_FIELDS: tuple[GoodsExportField, ...] = (
    "goods_code",
    "goods_name",
    "category_name",
    "spec",
    "unit",
    "reference_cost_price",
    "sale_price",
    "stock_min",
    "stock_max",
    "status",
    "remark",
    "created_time",
    "updated_time",
)


class GoodsExportSchema(BaseModel):
    """商品全量导出参数。"""

    query: GoodsQueryParam = Field(default_factory=GoodsQueryParam, description="商品查询条件")
    fields: list[GoodsExportField] = Field(default_factory=lambda: list(DEFAULT_GOODS_EXPORT_FIELDS), min_length=1, description="导出字段")
    format: Literal["xlsx", "csv"] = Field(default="xlsx", description="导出格式")
    sheet_name: str = Field(default="商品档案", max_length=31, description="工作表名称")

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: list[GoodsExportField]) -> list[GoodsExportField]:
        """按传入顺序去重导出字段。"""
        return list(dict.fromkeys(value))

    @field_validator("sheet_name")
    @classmethod
    def validate_sheet_name(cls, value: str) -> str:
        """清理工作表名称并拒绝 Excel 非法字符。"""
        result = value.strip() or "商品档案"
        if any(char in result for char in "[]:*?/\\"):
            raise ValueError("工作表名称不能包含 []:*?/\\")
        return result

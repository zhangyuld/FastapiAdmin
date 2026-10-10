import re
from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.base_schema import BaseQueryParam, BaseSchema, UserByQueryParam, UserBySchema


class SupplierBaseSchema(BaseModel):
    """供应商基础字段。"""

    supplier_name: str = Field(..., max_length=200, description="供应商名称")
    supplier_code: str = Field(..., max_length=64, description="供应商编码")
    contact: str = Field(..., max_length=64, description="联系人")
    phone: str = Field(..., max_length=20, description="联系电话")
    address: str | None = Field(default=None, max_length=200, description="地址")
    remark: str | None = Field(default=None, max_length=500, description="备注")
    status: int = Field(..., ge=0, le=1, description="状态(0:启用 1:停用)")


    @field_validator("supplier_name", "supplier_code")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """清理必填文本并拒绝纯空白内容。"""
        result = value.strip()
        if not result:
            raise ValueError("供应商名称和供应商编码不能为空")
        return result

    @field_validator("remark")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """清理可选文本，空白内容统一存储为空值。"""
        if value is None:
            return None
        return value.strip() or None


class SupplierCreateSchema(SupplierBaseSchema):
    """供应商创建参数。"""


class SupplierUpdateSchema(SupplierCreateSchema):
    """供应商修改参数。"""


class SupplierDeleteSchema(BaseModel):
    """供应商批量删除参数。"""

    ids: list[int] = Field(..., min_length=1, description="供应商ID列表")

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, value: list[int]) -> list[int]:
        """校验供应商ID为正整数并按传入顺序去重。"""
        if any(item < 1 for item in value):
            raise ValueError("供应商ID必须为正整数")
        return list(dict.fromkeys(value))


class SupplierStatusSchema(SupplierDeleteSchema):
    """供应商批量状态修改参数。"""

    status: int = Field(..., ge=0, le=1, description="状态(0:启用 1:停用)")


class SupplierOutSchema(SupplierBaseSchema, BaseSchema, UserBySchema):
    """供应商详情响应。"""

    model_config = ConfigDict(from_attributes=True)

    category_name: str | None = Field(default=None, description="供应商分类名称")


class SupplierQueryParam(BaseQueryParam, UserByQueryParam):
    """供应商查询参数。"""

    supplier_name: str | None = Field(default=None, max_length=200, description="供应商名称", json_schema_extra={"q": "like"})
    supplier_code: str | None = Field(default=None, max_length=64, description="供应商编码", json_schema_extra={"q": "like"})
    contact: str | None = Field(default=None, max_length=64, description="联系人", json_schema_extra={"q": "like"})
    phone: str | None = Field(default=None, max_length=20, description="联系电话", json_schema_extra={"q": "like"})
    status: int | None = Field(default=None, ge=0, le=1, description="状态(0:启用 1:停用)", json_schema_extra={"q": "eq"})


SupplierExportField = Literal[
    "supplier_code",
    "supplier_name",
    "contact",
    "phone",
    "address",
    "status",
    "remark",
    "created_time",
    "updated_time",
]

DEFAULT_SUPPLIER_EXPORT_FIELDS: tuple[SupplierExportField, ...] = (
    "supplier_code",
    "supplier_name",
    "contact",
    "phone",
    "address",
    "status",
    "remark",
    "created_time",
    "updated_time",
)


class SupplierExportSchema(BaseModel):
    """供应商全量导出参数。"""

    query: SupplierQueryParam = Field(default_factory=SupplierQueryParam, description="供应商查询条件")
    fields: list[SupplierExportField] = Field(default_factory=lambda: list(DEFAULT_SUPPLIER_EXPORT_FIELDS), min_length=1, description="导出字段")
    format: Literal["xlsx", "csv"] = Field(default="xlsx", description="导出格式")
    sheet_name: str = Field(default="供应商档案", max_length=31, description="工作表名称")
    filename: str | None = Field(default=None, max_length=200, description="导出文件名")

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: list[SupplierExportField]) -> list[SupplierExportField]:
        """按传入顺序去重导出字段。"""
        return list(dict.fromkeys(value))

    @field_validator("sheet_name")
    @classmethod
    def validate_sheet_name(cls, value: str) -> str:
        """清理工作表名称并拒绝 Excel 非法字符。"""
        result = value.strip() or "供应商档案"
        if any(char in result for char in "[]:*?/\\"):
            raise ValueError("工作表名称不能包含 []:*?/\\")
        return result

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str | None) -> str | None:
        """清理导出文件名并拒绝路径或系统非法字符。"""
        if value is None or not value.strip():
            return None
        result = re.sub(r"\.(xlsx|csv)$", "", value.strip(), flags=re.IGNORECASE)
        if not result:
            raise ValueError("导出文件名不能为空")
        if any(ord(char) < 32 or char in '<>:"/\\|?*' for char in result):
            raise ValueError('导出文件名不能包含 <>:"/\\|?* 或控制字符')
        return result

    def get_download_filename(self) -> str:
        """生成包含格式扩展名的最终下载文件名。"""
        base_name = self.filename or f"客户列表_{datetime.now():%Y%m%d_%H%M%S}"
        return f"{base_name}.{self.format}"

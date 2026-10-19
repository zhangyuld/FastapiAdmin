import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema, UserByQueryParam, UserBySchema


class WarehouseOptionSchema(BaseModel):
    """跨业务页面选项响应，仅包含标识、显示字段和状态。"""

    id: int
    warehouse_code: str
    warehouse_name: str
    status: int
    is_default: bool


class WarehouseBaseSchema(BaseModel):
    """仓库基础字段。"""

    warehouse_code: str = Field(..., max_length=64, description="仓库编码")
    warehouse_name: str = Field(..., max_length=200, description="仓库名称")
    address: str | None = Field(default=None, max_length=500, description="仓库地址")
    remark: str | None = Field(default=None, max_length=500, description="备注")
    status: int = Field(..., ge=0, le=1, description="状态(0:启用 1:停用)")

    @field_validator("warehouse_name", "warehouse_code")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """清理必填文本并拒绝纯空白内容。"""
        result = value.strip()
        if not result:
            raise ValueError("仓库名称和仓库编码不能为空")
        return result

    @field_validator("address", "remark")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """清理可选文本，空白内容统一存储为空值。"""
        if value is None:
            return None
        return value.strip() or None


class WarehouseCreateSchema(WarehouseBaseSchema):
    """仓库创建参数。"""


class WarehouseUpdateSchema(WarehouseCreateSchema):
    """仓库修改参数。"""


class WarehouseDeleteSchema(BaseModel):
    """仓库批量删除参数。"""

    ids: list[int] = Field(..., min_length=1, description="仓库ID列表")

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, value: list[int]) -> list[int]:
        """校验仓库ID为正整数并按传入顺序去重。"""
        if any(item < 1 for item in value):
            raise ValueError("仓库ID必须为正整数")
        return list(dict.fromkeys(value))


class WarehouseStatusSchema(WarehouseDeleteSchema):
    """仓库批量状态修改参数。"""

    status: int = Field(..., ge=0, le=1, description="状态(0:启用 1:停用)")


class WarehouseOutSchema(WarehouseBaseSchema, BaseSchema, UserBySchema):
    """仓库响应参数。"""

    model_config = ConfigDict(from_attributes=True)


class WarehouseQueryParam(BaseQueryParam, UserByQueryParam):
    """仓库查询参数。"""

    warehouse_code: str | None = Field(default=None, max_length=64, description="仓库编码", json_schema_extra={"q": "like"})
    warehouse_name: str | None = Field(default=None, max_length=200, description="仓库名称", json_schema_extra={"q": "like"})
    status: int | None = Field(default=None, ge=0, le=1, description="状态(0:启用 1:停用)", json_schema_extra={"q": "eq"})


WarehouseExportField = Literal[
    "warehouse_code",
    "warehouse_name",
    "address",
    "status",
    "remark",
    "created_time",
    "updated_time",
]

DEFAULT_WAREHOUSE_EXPORT_FIELDS: tuple[WarehouseExportField, ...] = (
    "warehouse_code",
    "warehouse_name",
    "address",
    "status",
    "remark",
    "created_time",
    "updated_time",
)


class WarehouseExportSchema(BaseModel):
    """仓库导出参数。"""

    query: WarehouseQueryParam = Field(default_factory=WarehouseQueryParam, description="仓库查询条件")
    fields: list[WarehouseExportField] = Field(
        default_factory=lambda: list(DEFAULT_WAREHOUSE_EXPORT_FIELDS),
        min_length=1,
        description="导出字段列表",
    )
    format: Literal["xlsx", "csv"] = Field(default="xlsx", description="导出格式")
    sheet_name: str = Field(default="仓库档案", max_length=31, description="工作表名称")
    filename: str | None = Field(default=None, max_length=200, description="导出文件名")

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: list[WarehouseExportField]) -> list[WarehouseExportField]:
        """按传入顺序去重导出字段。"""
        return list(dict.fromkeys(value))

    @field_validator("sheet_name")
    @classmethod
    def validate_sheet_name(cls, value: str) -> str:
        """清理工作表名称并拒绝 Excel 非法字符。"""
        result = value.strip() or "仓库档案"
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
        base_name = self.filename or f"仓库列表_{datetime.now():%Y%m%d_%H%M%S}"
        return f"{base_name}.{self.format}"

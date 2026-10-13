import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator

from app.core.base_schema import BaseQueryParam, BaseSchema, UserByQueryParam, UserBySchema
from app.core.validator import DateTimeStr

Quantity = Annotated[Decimal, Field(max_digits=18, decimal_places=3), PlainSerializer(lambda v: format(v, ".3f"), return_type=str, when_used="json")]
Price = Annotated[Decimal, Field(max_digits=18, decimal_places=4), PlainSerializer(lambda v: format(v, ".4f"), return_type=str, when_used="json")]
Amount = Annotated[Decimal, Field(max_digits=18, decimal_places=2), PlainSerializer(lambda v: format(v, ".2f"), return_type=str, when_used="json")]
PositiveId = Annotated[int, Field(gt=0, strict=True)]
Version = Annotated[int, Field(ge=0, strict=True)]


class OpeningLineInput(BaseModel):
    """期初仅接收数量与成本，金额和商品快照由后端生成。"""

    model_config = ConfigDict(extra="forbid")
    goods_id: PositiveId
    quantity: Quantity = Field(gt=0)
    unit_cost: Price = Field(ge=0)


class CheckLineInput(BaseModel):
    """盘点只接受实盘数量与零库存盘盈成本，不接受伪造快照。"""

    model_config = ConfigDict(extra="forbid")
    goods_id: PositiveId
    actual_quantity: Quantity = Field(ge=0)
    unit_cost: Price | None = Field(default=None, ge=0)


class OpeningCreateSchema(BaseModel):
    """期初草稿输入；初始化资格在确认时再次加锁校验。"""

    model_config = ConfigDict(extra="forbid")
    warehouse_id: PositiveId
    business_date: date
    remark: str | None = Field(default=None, max_length=500)
    items: list[OpeningLineInput] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_goods(self) -> Self:
        """同仓库单据不允许重复商品。"""
        if len({row.goods_id for row in self.items}) != len(self.items):
            raise ValueError("明细不能包含重复商品")
        return self


class CheckCreateSchema(OpeningCreateSchema):
    """盘点创建时读取服务端账面快照。"""

    items: list[CheckLineInput] = Field(min_length=1, max_length=500)


class OpeningUpdateSchema(OpeningCreateSchema):
    """期初完整草稿更新必须匹配当前版本。"""

    version: Version


class CheckUpdateSchema(CheckCreateSchema):
    """盘点更新保留原有商品快照，刷新需显式调用刷新接口。"""

    version: Version


class DocumentQuery(BaseQueryParam, UserByQueryParam):
    """期初及盘点主单查询，不包含分页。"""

    doc_no: str | None = Field(default=None, max_length=64)
    warehouse_id: int | None = Field(default=None, gt=0, json_schema_extra={"q": "eq"})
    status: Literal[0, 1, 2] | None = Field(default=None, json_schema_extra={"q": "eq"})
    business_date: list[date] | None = Field(default=None, min_length=2, max_length=2, json_schema_extra={"q": "between"})

    @field_validator("business_date")
    @classmethod
    def ordered_dates(cls, value: list[date] | None) -> list[date] | None:
        """拒绝逆序日期区间。"""
        if value and value[0] > value[1]:
            raise ValueError("开始日期不能晚于结束日期")
        return value


class VersionBody(BaseModel):
    """确认或刷新使用的单据并发版本。"""

    model_config = ConfigDict(extra="forbid")
    version: Version


class VoidBody(VersionBody):
    """冲销必须填写原因并匹配版本。"""

    void_reason: str = Field(min_length=1, max_length=500)

    @field_validator("void_reason")
    @classmethod
    def reason(cls, value: str) -> str:
        """拒绝纯空白作废原因。"""
        if not value.strip():
            raise ValueError("作废原因不能为空")
        return value.strip()


class DeleteBody(BaseModel):
    """批量删除只允许草稿，并精确提交各单版本。"""

    model_config = ConfigDict(extra="forbid")
    ids: list[PositiveId] = Field(min_length=1, max_length=500)
    versions: dict[Annotated[int, Field(gt=0)], Version]

    @model_validator(mode="after")
    def matching_versions(self) -> Self:
        """版本映射必须覆盖且只覆盖选中单据。"""
        self.ids = list(dict.fromkeys(self.ids))
        if set(self.ids) != set(self.versions):
            raise ValueError("版本映射与单据ID不匹配")
        return self


class StockItemOut(BaseModel):
    """期初和盘点商品快照及固化数量、成本。"""

    model_config = ConfigDict(from_attributes=True)
    id: int
    goods_id: int
    goods_code: str
    goods_name: str
    spec: str | None = None
    unit: str
    line_no: int | None = None
    quantity: Quantity | None = None
    unit_cost: Price
    cost_amount: Amount
    actual_quantity: Quantity | None = None
    system_quantity: Quantity | None = None
    difference_quantity: Quantity | None = None
    system_stock_amount: Amount | None = None
    balance_version: int | None = None


class StockDocumentOut(BaseSchema, UserBySchema):
    """库存业务主单；详情含商品明细，列表不加载明细。"""

    id: int
    doc_no: str
    warehouse_id: int
    warehouse_name: str
    business_date: date
    status: Literal[0, 1, 2]
    version: int
    remark: str | None = None
    confirmed_time: DateTimeStr | None = None
    voided_time: DateTimeStr | None = None
    confirmed_name: str | None = None
    voided_name: str | None = None
    void_reason: str | None = None
    items: list[StockItemOut] | None = None


class ExportOptions(BaseModel):
    """库存模块内导出公共文件参数，业务服务验证字段白名单。"""

    model_config = ConfigDict(extra="forbid")
    fields: list[str] = Field(min_length=1, max_length=40)
    format: Literal["xlsx", "csv"] = "xlsx"
    sheet_name: str = Field(default="库存", max_length=31)
    filename: str | None = Field(default=None, max_length=200)

    @field_validator("fields")
    @classmethod
    def unique_fields(cls, value: list[str]) -> list[str]:
        """保留选定导出字段的顺序并去重。"""
        return list(dict.fromkeys(value))

    @field_validator("sheet_name", "filename")
    @classmethod
    def safe_name(cls, value: str | None) -> str | None:
        """下载名称不能包含路径、控制字符或 Excel 非法字符。"""
        if value is None or not value.strip():
            return None if value is None else ""
        value = value.strip()
        if value in {".", ".."} or any(ord(c) < 32 or c in '<>:"/\\|?*[]' for c in value):
            raise ValueError("文件名或工作表名包含非法字符")
        return value

    def download_name(self, label: str) -> str:
        """空文件名按业务列表名和时间戳生成。"""
        base = re.sub(r"\.(xlsx|csv)$", "", self.filename or f"{label}列表_{datetime.now():%Y%m%d_%H%M%S}", flags=re.I)
        return f"{base}.{self.format}"


class DocumentExport(ExportOptions):
    """按有数据权限的主单筛选导出。"""

    query: DocumentQuery = Field(default_factory=DocumentQuery)

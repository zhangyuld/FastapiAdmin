import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator

from app.core.base_schema import BaseQueryParam, BaseSchema, UserByQueryParam, UserBySchema
from app.core.validator import DateTimeStr

# JSON 中固定小数位，Python 内保留 Decimal，避免金额经过浮点数转换。
PurchaseQuantity = Annotated[
    Decimal,
    Field(max_digits=18, decimal_places=3),
    PlainSerializer(lambda value: format(value, ".3f"), return_type=str, when_used="json"),
]
PurchasePrice = Annotated[
    Decimal,
    Field(max_digits=18, decimal_places=4),
    PlainSerializer(lambda value: format(value, ".4f"), return_type=str, when_used="json"),
]
PurchaseAmount = Annotated[
    Decimal,
    Field(max_digits=18, decimal_places=2),
    PlainSerializer(lambda value: format(value, ".2f"), return_type=str, when_used="json"),
]
PositiveId = Annotated[int, Field(gt=0, strict=True)]
PurchaseVersion = Annotated[int, Field(ge=0, strict=True)]


class PurchaseInItemCreateSchema(BaseModel):
    """草稿商品明细，只接收商品 ID、数量和采购单价。"""

    model_config = ConfigDict(extra="forbid")

    goods_id: PositiveId = Field(description="商品ID")
    quantity: PurchaseQuantity = Field(gt=0, description="采购数量，最多三位小数")
    unit_price: PurchasePrice = Field(ge=0, description="采购单价，最多四位小数")


class PurchaseInCreateSchema(BaseModel):
    """新建采购入库草稿；单号、商品快照和金额由业务层生成。"""

    model_config = ConfigDict(extra="forbid")

    supplier_id: PositiveId = Field(description="供应商ID")
    warehouse_id: PositiveId = Field(description="入库仓库ID")
    business_date: date = Field(description="业务日期")
    remark: str | None = Field(default=None, max_length=500, description="备注")
    items: list[PurchaseInItemCreateSchema] = Field(min_length=1, description="采购商品明细")

    @field_validator("remark")
    @classmethod
    def normalize_remark(cls, value: str | None) -> str | None:
        """去除备注两端空白，空内容统一为空值。"""
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def validate_unique_goods(self) -> Self:
        """拒绝同一草稿中的重复商品。"""
        goods_ids = [item.goods_id for item in self.items]
        if len(goods_ids) != len(set(goods_ids)):
            raise ValueError("采购明细不能包含重复商品")
        return self


class PurchaseInUpdateSchema(PurchaseInCreateSchema):
    """完整更新草稿，必须提交全部明细及当前版本。"""

    version: PurchaseVersion = Field(description="当前乐观锁版本")


class PurchaseInQueryParam(BaseQueryParam, UserByQueryParam):
    """采购入库筛选条件，分页使用独立的 PaginationQueryParam。"""

    order_no: str | None = Field(default=None, max_length=64, description="采购入库单号", json_schema_extra={"q": "like"})
    supplier_id: int | None = Field(default=None, gt=0, description="供应商ID", json_schema_extra={"q": "eq"})
    warehouse_id: int | None = Field(default=None, gt=0, description="仓库ID", json_schema_extra={"q": "eq"})
    business_date: list[date] | None = Field(default=None, min_length=2, max_length=2, description="业务日期范围，开始日期和结束日期", json_schema_extra={"q": "between"})
    status: int | None = Field(default=None, ge=0, le=2, description="状态(0:草稿 1:已确认 2:已作废)", json_schema_extra={"q": "eq"})

    @field_validator("order_no")
    @classmethod
    def normalize_order_no(cls, value: str | None) -> str | None:
        """空白单号不参与筛选。"""
        if value is None:
            return None
        return value.strip() or None

    @field_validator("business_date")
    @classmethod
    def validate_business_date(cls, value: list[date] | None) -> list[date] | None:
        """日期区间必须按开始、结束顺序传入。"""
        if value is not None and value[0] > value[1]:
            raise ValueError("开始日期不能晚于结束日期")
        return value


class PurchaseInItemOutSchema(BaseModel):
    """采购明细响应，商品信息为保存时的快照。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(gt=0, description="入库明细ID")
    line_no: int = Field(gt=0, description="行号")
    goods_id: int = Field(gt=0, description="商品ID")
    goods_code: str = Field(max_length=64, description="商品编码快照")
    goods_name: str = Field(max_length=200, description="商品名称快照")
    spec: str | None = Field(default=None, max_length=200, description="规格型号快照")
    unit: str = Field(max_length=32, description="单位快照")
    quantity: PurchaseQuantity = Field(gt=0, description="采购数量")
    unit_price: PurchasePrice = Field(ge=0, description="采购单价")
    line_amount: PurchaseAmount = Field(ge=0, description="行金额")


class PurchaseInOutSchema(BaseSchema, UserBySchema):
    """采购列表记录，不加载商品明细；关联名称由业务层补充。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(gt=0, description="采购入库单ID")
    order_no: str = Field(max_length=64, description="采购入库单号")
    supplier_id: int = Field(gt=0, description="供应商ID")
    supplier_name: str = Field(description="供应商名称")
    warehouse_id: int = Field(gt=0, description="仓库ID")
    warehouse_name: str = Field(description="仓库名称")
    business_date: date = Field(description="业务日期")
    total_amount: PurchaseAmount = Field(ge=0, description="采购总额")
    status: Literal[0, 1, 2] = Field(description="状态(0:草稿 1:已确认 2:已作废)")
    version: int = Field(ge=0, description="当前乐观锁版本")
    remark: str | None = Field(default=None, max_length=500, description="备注")
    confirmed_id: int | None = Field(default=None, gt=0, description="确认人ID")
    confirmed_name: str | None = Field(default=None, description="确认人名称")
    confirmed_time: DateTimeStr | None = Field(default=None, description="确认时间")
    voided_id: int | None = Field(default=None, gt=0, description="作废人ID")
    voided_name: str | None = Field(default=None, description="作废人名称")
    voided_time: DateTimeStr | None = Field(default=None, description="作废时间")
    void_reason: str | None = Field(default=None, max_length=500, description="作废原因")


class PurchaseInDetailItemOutSchema(PurchaseInItemOutSchema):
    """入库详情展示有效退货数量，不改变原采购数量。"""

    returned_quantity: PurchaseQuantity = Field(ge=0, description="已确认未作废的退货数量")
    returnable_quantity: PurchaseQuantity = Field(ge=0, description="剩余可退数量，未确认入库为零")


class PurchaseInReturnSummarySchema(BaseModel):
    """跨退货数据范围统计原单实际退货情况，不暴露下游单据身份。"""

    return_status: Literal["none", "partial", "full"] = Field(description="未退、部分退、全部退")
    confirmed_count: int = Field(ge=0, description="有效已确认退货单数")
    returned_amount: PurchaseAmount = Field(ge=0, description="有效退货金额")


class PurchaseInRelatedReturnOutSchema(BaseModel):
    """有退货数据权限的关联单据摘要。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    order_no: str
    business_date: date
    status: Literal[0, 1, 2]
    total_amount: PurchaseAmount
    return_reason: str
    confirmed_time: DateTimeStr | None = None


class PurchaseInDetailOutSchema(PurchaseInOutSchema):
    """完整单据响应，详情及保存响应需显式提供明细。"""

    items: list[PurchaseInDetailItemOutSchema] = Field(min_length=1, description="采购商品明细及退货数量")
    return_summary: PurchaseInReturnSummarySchema = Field(description="原单实际退货汇总")


class PurchaseInDeleteSchema(BaseModel):
    """批量删除草稿，逐单据携带版本以防并发误删。"""

    model_config = ConfigDict(extra="forbid")

    ids: list[PositiveId] = Field(min_length=1, description="采购入库单ID列表")
    # JSON 对象键为字符串，键允许转为整数，版本值必须为真正的非负整数。
    versions: dict[Annotated[int, Field(gt=0)], PurchaseVersion] = Field(min_length=1, description="单据ID与当前版本映射")

    @field_validator("ids")
    @classmethod
    def deduplicate_ids(cls, value: list[int]) -> list[int]:
        """按传入顺序去重待删除单据。"""
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_versions(self) -> Self:
        """每个待删除单据必须有且仅有一个版本。"""
        if set(self.ids) != set(self.versions):
            raise ValueError("版本映射必须与待删除单据ID完全对应")
        return self


class PurchaseInConfirmSchema(BaseModel):
    """确认单据参数，状态与版本匹配由业务层校验。"""

    model_config = ConfigDict(extra="forbid")

    version: PurchaseVersion = Field(description="当前乐观锁版本")


class PurchaseInVoidSchema(PurchaseInConfirmSchema):
    """作废已确认单据，必须提供原因。"""

    void_reason: str = Field(min_length=1, max_length=500, description="作废原因")

    @field_validator("void_reason")
    @classmethod
    def validate_void_reason(cls, value: str) -> str:
        """作废原因不允许纯空白。"""
        result = value.strip()
        if not result:
            raise ValueError("作废原因不能为空")
        return result


PurchaseInExportField = Literal[
    "order_no",
    "supplier_name",
    "warehouse_name",
    "business_date",
    "total_amount",
    "status",
    "created_name",
    "confirmed_time",
]
DEFAULT_PURCHASE_IN_EXPORT_FIELDS: tuple[PurchaseInExportField, ...] = (
    "order_no",
    "supplier_name",
    "warehouse_name",
    "business_date",
    "total_amount",
    "status",
    "created_name",
    "confirmed_time",
)


class PurchaseInExportSchema(BaseModel):
    """全量导出入参，字段与前端采购列表导出白名单一致。"""

    model_config = ConfigDict(extra="forbid")

    query: PurchaseInQueryParam = Field(default_factory=PurchaseInQueryParam, description="查询条件，不含分页")
    fields: list[PurchaseInExportField] = Field(default_factory=lambda: list(DEFAULT_PURCHASE_IN_EXPORT_FIELDS), min_length=1, description="按顺序导出的字段")
    format: Literal["xlsx", "csv"] = Field(default="xlsx", description="文件格式")
    sheet_name: str = Field(default="采购入库", min_length=1, max_length=31, description="工作表名称")
    filename: str | None = Field(default=None, max_length=200, description="导出文件名，不填时自动生成")

    @field_validator("fields")
    @classmethod
    def deduplicate_fields(cls, value: list[PurchaseInExportField]) -> list[PurchaseInExportField]:
        """保留用户指定的导出顺序并去重。"""
        return list(dict.fromkeys(value))

    @field_validator("sheet_name")
    @classmethod
    def validate_sheet_name(cls, value: str) -> str:
        """清理工作表名称并拒绝 Excel 非法字符和控制字符。"""
        result = value.strip() or "采购入库"
        if any(ord(char) < 32 or char in "[]:*?/\\\\" for char in result):
            raise ValueError("工作表名称包含非法字符")
        return result

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str | None) -> str | None:
        """清理文件名、移除已填写的扩展名并拒绝路径或非法字符。"""
        if value is None or not value.strip():
            return None
        result = re.sub(r"\.(xlsx|csv)$", "", value.strip(), flags=re.IGNORECASE)
        if not result or result in {".", ".."}:
            raise ValueError("导出文件名无效")
        if any(ord(char) < 32 or char in '<>:"/\\\\|?*' for char in result):
            raise ValueError("导出文件名包含非法字符")
        return result

    def get_download_filename(self) -> str:
        """生成带文件格式扩展名的下载名称。"""
        base_name = self.filename or f"采购入库列表_{datetime.now():%Y%m%d_%H%M%S}"
        return f"{base_name}.{self.format}"


class PurchaseInReturnableQueryParam(BaseModel):
    """读取可退数量时可排除当前退货草稿，业务层必须校验归属。"""

    exclude_return_id: int | None = Field(default=None, gt=0, description="当前采购退货草稿ID")


class PurchaseInReturnableItemOutSchema(PurchaseInDetailItemOutSchema):
    """来源入库明细及业务层计算的实时可退数量。"""

    returnable_quantity: PurchaseQuantity = Field(ge=0, description="当前可退数量")


class PurchaseInReturnableOutSchema(PurchaseInDetailOutSchema):
    """采购退货选择来源入库单的响应。"""

    items: list[PurchaseInReturnableItemOutSchema] = Field(min_length=1, description="带可退数量的来源明细")

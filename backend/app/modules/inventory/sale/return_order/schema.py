from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.base_schema import BaseSchema, UserBySchema
from app.core.validator import DateTimeStr

from ..out import schema as _out_schema

# 复用销售域的金额精度、审计筛选及版本校验，不继承出库金额字段。
PositiveId = _out_schema.PositiveId
SaleVersion = _out_schema.SaleVersion
SalePrice = _out_schema.SalePrice
SaleAmount = _out_schema.SaleAmount
SaleQuantity = _out_schema.SaleQuantity


class SaleReturnItemCreateSchema(_out_schema.SaleOutItemCreateSchema):
    """原单退货明细，必须提供来源行，单价由后端与原单核对。"""

    source_sale_out_item_id: PositiveId = Field(description="原销售出库明细ID")


class SaleReturnCreateSchema(BaseModel):
    """原单退货草稿输入，不接收金额、成本、商品快照或审计字段。"""

    model_config = ConfigDict(extra="forbid")

    customer_id: PositiveId = Field(description="来源客户ID")
    warehouse_id: PositiveId = Field(description="来源仓库ID")
    source_sale_out_id: PositiveId = Field(description="已确认的原销售出库单ID")
    business_date: date = Field(description="退货业务日期")
    return_reason: str = Field(min_length=1, max_length=500, description="退货原因")
    remark: str | None = Field(default=None, max_length=500, description="备注")
    items: list[SaleReturnItemCreateSchema] = Field(min_length=1, description="退货明细")

    @field_validator("return_reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        """拒绝空白退货原因。"""
        if not value.strip():
            raise ValueError("退货原因不能为空")
        return value.strip()

    @field_validator("remark")
    @classmethod
    def normalize_remark(cls, value: str | None) -> str | None:
        """空备注统一保存为空值。"""
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_unique_sources(self) -> Self:
        """同一来源行只能出现一次，避免重复退货和重复金额分摊。"""
        ids = [item.source_sale_out_item_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("退货明细不能包含重复来源行")
        return self


class SaleReturnUpdateSchema(SaleReturnCreateSchema):
    """完整更新退货草稿及当前版本。"""

    version: SaleVersion = Field(description="当前乐观锁版本")


class SaleReturnQueryParam(_out_schema.SaleOutQueryParam):
    """退货筛选条件，来源单号由 CRUD 转换成来源子查询。"""

    source_order_no: str | None = Field(default=None, max_length=64, description="原销售出库单号", json_schema_extra={"q": "like"})

    @field_validator("source_order_no")
    @classmethod
    def normalize_source_order_no(cls, value: str | None) -> str | None:
        """空白来源单号不参与筛选。"""
        return value.strip() or None if value is not None else None


class SaleReturnItemOutSchema(_out_schema.SaleOutItemOutSchema):
    """来源商品快照和本次固化的退货金额、成本。"""

    source_sale_out_item_id: int | None = Field(default=None, gt=0, description="原出库明细ID")
    unit_cost: SalePrice = Field(ge=0, description="原入账单位成本")
    cost_amount: SaleAmount = Field(ge=0, description="本次分摊成本")
    returnable_quantity: SaleQuantity | None = Field(default=None, ge=0, description="草稿当前可退数量")


class SaleReturnOutSchema(BaseSchema, UserBySchema):
    """退货列表响应，来源允许为空以兼容历史记录，新增不允许无来源。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(gt=0, description="销售退货单ID")
    order_no: str = Field(max_length=64, description="销售退货单号")
    customer_id: int = Field(gt=0, description="客户ID")
    customer_name: str = Field(description="客户名称")
    warehouse_id: int = Field(gt=0, description="仓库ID")
    warehouse_name: str = Field(description="仓库名称")
    business_date: date = Field(description="退货业务日期")
    return_amount: SaleAmount = Field(ge=0, description="优惠分摊后的退货金额")
    status: Literal[0, 1, 2] = Field(description="草稿、已确认、已作废")
    version: int = Field(ge=0, description="当前版本")
    remark: str | None = Field(default=None, max_length=500, description="备注")
    confirmed_id: int | None = Field(default=None, gt=0, description="确认人ID")
    confirmed_name: str | None = Field(default=None, description="确认人名称")
    confirmed_time: DateTimeStr | None = Field(default=None, description="确认时间")
    voided_id: int | None = Field(default=None, gt=0, description="作废人ID")
    voided_name: str | None = Field(default=None, description="作废人名称")
    voided_time: DateTimeStr | None = Field(default=None, description="作废时间")
    void_reason: str | None = Field(default=None, max_length=500, description="作废原因")

    source_sale_out_id: int | None = Field(default=None, gt=0, description="原出库单ID")
    source_order_no: str | None = Field(default=None, description="原出库单号")
    return_reason: str = Field(description="退货原因")


class SaleReturnDetailOutSchema(SaleReturnOutSchema):
    """退货详情及保存响应。"""

    items: list[SaleReturnItemOutSchema] = Field(min_length=1, description="退货明细")


class SaleReturnDeleteSchema(_out_schema.SaleOutDeleteSchema):
    """批量删除退货草稿，ID 与版本映射必须完全对应。"""


class SaleReturnConfirmSchema(_out_schema.SaleOutConfirmSchema):
    """退货确认参数。"""


class SaleReturnVoidSchema(_out_schema.SaleOutVoidSchema):
    """退货作废参数，版本及原因必填。"""


SaleReturnExportField = Literal[
    "order_no",
    "customer_name",
    "warehouse_name",
    "business_date",
    "source_order_no",
    "return_reason",
    "return_amount",
    "status",
    "created_name",
    "confirmed_time",
]
RETURN_EXPORT_FIELDS = (
    "order_no",
    "customer_name",
    "warehouse_name",
    "business_date",
    "source_order_no",
    "return_reason",
    "return_amount",
    "status",
    "created_name",
    "confirmed_time",
)


class SaleReturnExportSchema(_out_schema.SaleOutExportSchema):
    """按字段顺序导出退货，复用销售文件名和工作表的合法性校验。"""

    query: SaleReturnQueryParam = Field(default_factory=SaleReturnQueryParam)
    fields: list[SaleReturnExportField] = Field(default_factory=lambda: list(RETURN_EXPORT_FIELDS), min_length=1)
    sheet_name: str = Field(default="销售退货", min_length=1, max_length=31)

    @field_validator("sheet_name", mode="before")
    @classmethod
    def normalize_return_sheet_name(cls, value: str) -> str:
        """空白工作表名回退到退货名称，非法字符仍由销售域校验器拒绝。"""
        return value.strip() or "销售退货" if isinstance(value, str) else value

    def get_download_filename(self) -> str:
        """未指定文件名时使用销售退货列表及时间戳。"""
        return f"{self.filename or f'销售退货列表_{datetime.now():%Y%m%d_%H%M%S}'}.{self.format}"

from datetime import date, datetime
from importlib import import_module
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# in、return 均为 Python 关键字，模块间复用采购精度和版本契约时通过模块路径加载。
_in_schema = import_module("app.modules.inventory.purchase.in.schema")
PositiveId = _in_schema.PositiveId
PurchaseVersion = _in_schema.PurchaseVersion
PurchasePrice = _in_schema.PurchasePrice
PurchaseAmount = _in_schema.PurchaseAmount
PurchaseQuantity = _in_schema.PurchaseQuantity


class PurchaseReturnItemCreateSchema(_in_schema.PurchaseInItemCreateSchema):
    """原单退货明细，必须提供来源行，单价由后端与原单核对。"""

    source_purchase_in_item_id: PositiveId = Field(description="原采购入库明细ID")


class PurchaseReturnCreateSchema(BaseModel):
    """原单退货草稿输入，不接收金额、成本、商品快照或审计字段。"""

    model_config = ConfigDict(extra="forbid")

    supplier_id: PositiveId = Field(description="来源供应商ID")
    warehouse_id: PositiveId = Field(description="来源仓库ID")
    source_purchase_in_id: PositiveId = Field(description="已确认的原采购入库单ID")
    business_date: date = Field(description="退货业务日期")
    return_reason: str = Field(min_length=1, max_length=500, description="退货原因")
    remark: str | None = Field(default=None, max_length=500, description="备注")
    items: list[PurchaseReturnItemCreateSchema] = Field(min_length=1, description="退货明细")

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
        ids = [item.source_purchase_in_item_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("退货明细不能包含重复来源行")
        return self


class PurchaseReturnUpdateSchema(PurchaseReturnCreateSchema):
    """完整更新退货草稿及当前版本。"""

    version: PurchaseVersion = Field(description="当前乐观锁版本")


class PurchaseReturnQueryParam(_in_schema.PurchaseInQueryParam):
    """退货筛选条件，来源单号由 CRUD 转换成来源子查询。"""

    source_order_no: str | None = Field(default=None, max_length=64, description="原采购入库单号", json_schema_extra={"q": "like"})

    @field_validator("source_order_no")
    @classmethod
    def normalize_source_order_no(cls, value: str | None) -> str | None:
        """空白来源单号不参与筛选。"""
        return value.strip() or None if value is not None else None


class PurchaseReturnItemOutSchema(_in_schema.PurchaseInItemOutSchema):
    """来源商品快照和本次固化的退货金额、成本。"""

    source_purchase_in_item_id: int | None = Field(default=None, gt=0, description="原入库明细ID")
    unit_cost: PurchasePrice = Field(ge=0, description="原入账单位成本")
    cost_amount: PurchaseAmount = Field(ge=0, description="本次分摊成本")
    returnable_quantity: PurchaseQuantity | None = Field(default=None, ge=0, description="草稿当前可退数量")


class PurchaseReturnOutSchema(_in_schema.PurchaseInOutSchema):
    """退货列表响应，来源允许为空以兼容历史记录，新增不允许无来源。"""

    source_purchase_in_id: int | None = Field(default=None, gt=0, description="原入库单ID")
    source_order_no: str | None = Field(default=None, description="原入库单号")
    return_reason: str = Field(description="退货原因")


class PurchaseReturnDetailOutSchema(PurchaseReturnOutSchema):
    """退货详情及保存响应。"""

    items: list[PurchaseReturnItemOutSchema] = Field(min_length=1, description="退货明细")


class PurchaseReturnDeleteSchema(_in_schema.PurchaseInDeleteSchema):
    """批量删除退货草稿，ID 与版本映射必须完全对应。"""


class PurchaseReturnConfirmSchema(_in_schema.PurchaseInConfirmSchema):
    """退货确认参数。"""


class PurchaseReturnVoidSchema(_in_schema.PurchaseInVoidSchema):
    """退货作废参数，版本及原因必填。"""


PurchaseReturnExportField = Literal[
    "order_no",
    "supplier_name",
    "warehouse_name",
    "business_date",
    "source_order_no",
    "return_reason",
    "total_amount",
    "status",
    "created_name",
    "confirmed_time",
]
RETURN_EXPORT_FIELDS = (
    "order_no",
    "supplier_name",
    "warehouse_name",
    "business_date",
    "source_order_no",
    "return_reason",
    "total_amount",
    "status",
    "created_name",
    "confirmed_time",
)


class PurchaseReturnExportSchema(_in_schema.PurchaseInExportSchema):
    """按字段顺序导出退货，复用采购文件名和工作表的合法性校验。"""

    query: PurchaseReturnQueryParam = Field(default_factory=PurchaseReturnQueryParam)
    fields: list[PurchaseReturnExportField] = Field(default_factory=lambda: list(RETURN_EXPORT_FIELDS), min_length=1)
    sheet_name: str = Field(default="采购退货", min_length=1, max_length=31)

    def get_download_filename(self) -> str:
        """未指定文件名时使用采购退货列表及时间戳。"""
        return f"{self.filename or f'采购退货列表_{datetime.now():%Y%m%d_%H%M%S}'}.{self.format}"

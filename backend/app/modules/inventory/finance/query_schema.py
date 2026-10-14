import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema, UserByQueryParam, UserBySchema

Money = Annotated[Decimal, PlainSerializer(lambda value: format(value, ".2f"), return_type=str, when_used="json")]
FinanceKind = Literal["receivable", "payable"]


class PartyQuery(BaseModel):
    """余额按往来对象查询，不混入日期或单据状态造成余额口径变化。"""

    party_id: int | None = Field(default=None, gt=0)
    party_code: str | None = Field(default=None, max_length=64)
    party_name: str | None = Field(default=None, max_length=200)


class BalanceQuery(PartyQuery):
    """当前余额只对有账单的对象汇总，正负余额分开显示。"""

    balance_state: Literal["positive", "negative", "zero"] | None = None


class BillQuery(PartyQuery, BaseQueryParam, UserByQueryParam):
    """账单筛选与余额独立，核销状态不等于业务单据状态。"""

    business_type: Literal["sale_out", "sale_return", "purchase_in", "purchase_return"] | None = None
    operation_type: Literal["confirm", "void"] | None = None
    business_no: str | None = Field(default=None, max_length=64)
    bill_date: list[date] | None = Field(default=None, min_length=2, max_length=2)
    status: Literal[0, 1, 2] | None = None
    reversal_state: Literal["original", "reversed", "reversal"] | None = None

    @field_validator("bill_date", "created_time", "updated_time")
    @classmethod
    def ordered_range(cls, value: list | None) -> list | None:
        """拒绝不完整和逆序区间，保持列表及导出相同筛选口径。"""
        if value and (len(value) != 2 or value[0] > value[1]):
            raise ValueError("日期区间必须按起止顺序传入两个值")
        return value


class BillOut(BaseSchema, UserBySchema):
    """应收应付只读账单，金额有方向，核销字段为绝对值。"""

    id: int
    party_id: int
    party_code: str
    party_name: str
    business_type: str
    operation_type: Literal["confirm", "void"]
    business_id: int
    business_no: str
    amount: Money
    allocated_amount: Money
    unallocated_amount: Money
    bill_date: date
    status: Literal[0, 1, 2]
    reversal_id: int | None
    reversal_state: Literal["original", "reversed", "reversal"]
    remark: str | None


class BillDetail(BillOut):
    """冲销详情关联原账单，原账单详情关联所有未删除冲销账单。"""

    related_bills: list[BillOut] = Field(default_factory=list)


class BalanceOut(BaseModel):
    """同一对象的业务净额与带方向未核销净额，不跨对象抵消待收待付。"""

    id: int
    party_id: int
    party_code: str
    party_name: str
    business_net_amount: Money
    allocated_net_amount: Money
    unsettled_net_amount: Money
    bill_count: int


class SummaryOut(BaseModel):
    """余额视图下全部对象的汇总，与分页大小无关。"""

    party_count: int
    business_net_amount: Money
    unsettled_net_amount: Money
    positive_balance: Money
    negative_balance: Money


class ExportOptions(BaseModel):
    """往来模块内文件参数，不复用库存模块私有 Schema。"""

    model_config = ConfigDict(extra="forbid")
    fields: list[str] = Field(min_length=1, max_length=40)
    format: Literal["xlsx", "csv"] = "xlsx"
    sheet_name: str = Field(default="往来", max_length=31)
    filename: str | None = Field(default=None, max_length=200)

    @field_validator("fields")
    @classmethod
    def unique_fields(cls, value: list[str]) -> list[str]:
        """保留选定字段顺序并去重。"""
        return list(dict.fromkeys(value))

    @field_validator("sheet_name", "filename")
    @classmethod
    def safe_name(cls, value: str | None) -> str | None:
        """拒绝文件路径、控制字符与工作表非法字符。"""
        if value is None or not value.strip():
            return None if value is None else ""
        value = value.strip()
        if value in {".", ".."} or any(ord(char) < 32 or char in '<>:"/\\|?*[]' for char in value):
            raise ValueError("文件名或工作表名包含非法字符")
        return value

    def download_name(self, label: str) -> str:
        """空文件名生成业务名称加时间戳，扩展名与格式一致。"""
        base = re.sub(r"\.(xlsx|csv)$", "", self.filename or f"{label}列表_{datetime.now():%Y%m%d_%H%M%S}", flags=re.I)
        return f"{base}.{self.format}"


class BillExport(ExportOptions):
    """全部账单导出与账单列表使用相同筛选。"""

    query: BillQuery = Field(default_factory=BillQuery)


class BalanceExport(ExportOptions):
    """全部余额导出与余额视图使用相同筛选。"""

    query: BalanceQuery = Field(default_factory=BalanceQuery)

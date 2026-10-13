from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema, UserByQueryParam, UserBySchema
from app.core.validator import DateTimeStr
from app.modules.inventory.enums import BusinessOperationType, StockBusinessType

from .document_schema import Amount, ExportOptions, Price, Quantity


class StockQuery(BaseQueryParam, UserByQueryParam):
    """共享库存筛选支持档案名称和审计条件，不按创建人限制数据范围。"""

    goods_id: int | None = Field(default=None, gt=0)
    goods_code: str | None = Field(default=None, max_length=64)
    goods_name: str | None = Field(default=None, max_length=200)
    category_id: int | None = Field(default=None, gt=0)
    warehouse_id: int | None = Field(default=None, gt=0)
    warehouse_name: str | None = Field(default=None, max_length=100)


class BalanceQuery(StockQuery):
    """当前库存的零库存及上下限预警筛选。"""

    quantity_state: Literal["positive", "zero"] | None = None
    warning: Literal["low", "high"] | None = None


class LogQuery(StockQuery):
    """库存流水区分业务日期与实际入账时间，支持来源与操作筛选。"""

    business_type: StockBusinessType | None = None
    operation_type: BusinessOperationType | None = None
    business_no: str | None = Field(default=None, max_length=64)
    business_date: list[date] | None = Field(default=None, min_length=2, max_length=2)
    posted_time: list[datetime] | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("business_date", "posted_time")
    @classmethod
    def ordered_range(cls, value: list | None) -> list | None:
        """时间区间必须按开始和结束顺序传入。"""
        if value and value[0] > value[1]:
            raise ValueError("开始时间不能晚于结束时间")
        return value


class BalanceOut(BaseSchema, UserBySchema):
    """已建立的仓库商品余额，不通过商品与仓库笛卡尔积伪造余额。"""

    id: int
    warehouse_id: int
    warehouse_name: str
    goods_id: int
    goods_code: str
    goods_name: str
    category_id: int | None
    spec: str | None
    unit: str
    quantity: Quantity
    avg_cost: Price
    stock_amount: Amount
    stock_min: Quantity
    stock_max: Quantity
    warning: Literal["normal", "low", "high"]
    last_business_time: DateTimeStr | None
    version: int


class LogOut(BaseSchema, UserBySchema):
    """不可变库存流水及来源标识；来源单据读取另行授权。"""

    id: int
    warehouse_id: int
    warehouse_name: str
    goods_id: int
    goods_code: str
    goods_name: str
    spec: str | None
    unit: str
    business_type: StockBusinessType
    operation_type: BusinessOperationType
    business_id: int
    business_item_id: int
    business_no: str
    business_date: date
    before_quantity: Quantity
    change_quantity: Quantity
    after_quantity: Quantity
    unit_cost: Price
    cost_amount: Amount
    posted_time: DateTimeStr
    reversal_log_id: int | None
    remark: str | None


class BalanceExport(ExportOptions):
    """当前库存全量导出与列表共用筛选。"""

    query: BalanceQuery = Field(default_factory=BalanceQuery)


class LogExport(ExportOptions):
    """流水全量导出保留来源、日期及字段顺序。"""

    query: LogQuery = Field(default_factory=LogQuery)

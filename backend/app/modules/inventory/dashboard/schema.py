"""经营首页的只读响应，未授权领域返回空值而非零金额。"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.inventory.report.stock.schema import Money, Quantity

BusinessKind = Literal["purchase_in", "purchase_return", "sale_out", "sale_return"]


class TradeMetric(BaseModel):
    """期间净额及独立退货金额，不表示实际资金收付。"""

    net_amount: Money
    return_amount: Money


class FinanceMetric(BaseModel):
    """按对象净额计算的正向待收待付和负向冲减余额。"""

    positive_balance: Money
    negative_balance: Money


class DashboardSummary(BaseModel):
    """日期采用北京时间，当前余额不受期间条件影响。"""

    as_of: datetime
    today: date
    sale_today: TradeMetric | None = None
    sale_month: TradeMetric | None = None
    purchase_today: TradeMetric | None = None
    purchase_month: TradeMetric | None = None
    stock_amount: Money | None = None
    warning_count: int | None = None
    receivable: FinanceMetric | None = None
    payable: FinanceMetric | None = None


class TrendQuery(BaseModel):
    """限定预置期间，避免无界趋势请求。"""

    period: Literal["7d", "30d", "month"] = "30d"


class TrendPoint(BaseModel):
    """已授权领域无业务的日期补零，未授权领域始终为空。"""

    business_date: date
    sale_amount: Money | None = None
    purchase_amount: Money | None = None


class TrendOut(BaseModel):
    """趋势期间及其逐日净额。"""

    start_date: date
    end_date: date
    points: list[TrendPoint]


class WarehouseStock(BaseModel):
    """只统计已有库存记录的仓库，不生成未建账组合。"""

    warehouse_id: int
    warehouse_name: str
    stock_amount: Money


class WarningQuery(BaseModel):
    """预警列表固定稳定排序，仅开放有界分页。"""

    page_no: int = Field(default=1, ge=1)
    page_size: int = Field(default=5, ge=1, le=50)


class StockWarningOut(BaseModel):
    """商品与仓库为预警身份，数量不可跨单位相加。"""

    id: str
    warehouse_id: int
    warehouse_name: str
    goods_id: int
    goods_code: str
    goods_name: str
    unit: str
    quantity: Quantity
    stock_min: Quantity
    stock_max: Quantity
    warning: Literal["low", "high"]


class RecentQuery(BaseModel):
    """最近单据按创建时间排序，限制首页读取数量。"""

    limit: int = Field(default=8, ge=1, le=20)


class RecentDocument(BaseModel):
    """来源类型和 ID 联合标识单据，详情仍需原业务授权。"""

    id: str
    business_type: BusinessKind
    business_id: int
    business_no: str
    business_date: date
    created_time: datetime
    amount: Money
    status: Literal[0, 1, 2]

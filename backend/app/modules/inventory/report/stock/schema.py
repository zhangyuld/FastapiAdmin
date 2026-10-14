import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator

Money = Annotated[Decimal, PlainSerializer(lambda value: format(value, ".2f"), return_type=str, when_used="json")]
Quantity = Annotated[Decimal, PlainSerializer(lambda value: format(value, ".3f"), return_type=str, when_used="json")]
UnitCost = Annotated[Decimal, PlainSerializer(lambda value: format(value, ".4f"), return_type=str, when_used="json")]
StockWarning = Literal["normal", "low", "high"]


class StockReportQuery(BaseModel):
    """余额不接受期间日期，流水期间变动不接受余额预警。"""

    view: Literal["balance", "movement"] = "balance"
    business_date: list[date] | None = Field(default=None, min_length=2, max_length=2)
    warehouse_id: int | None = Field(default=None, gt=0)
    warehouse_name: str | None = Field(default=None, max_length=100)
    category_id: int | None = Field(default=None, gt=0)
    category_name: str | None = Field(default=None, max_length=100)
    goods_code: str | None = Field(default=None, max_length=64)
    goods_name: str | None = Field(default=None, max_length=200)
    warning: StockWarning | None = None

    @field_validator("warehouse_name", "category_name", "goods_code", "goods_name")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        """空输入不产生档案筛选，查询层转义文本通配字符。"""
        return value.strip() or None if value is not None else None

    @field_validator("business_date")
    @classmethod
    def ordered_dates(cls, value: list[date] | None) -> list[date] | None:
        """期间必须为完整有序区间，不将逆序日期静默改成无筛选。"""
        if value and value[0] > value[1]:
            raise ValueError("业务日期必须按起止顺序传入")
        return value

    @model_validator(mode="after")
    def validate_view_filters(self) -> Self:
        """拒绝跨视图条件，不将当前库存误解为历史时点库存。"""
        if self.view == "balance" and self.business_date is not None:
            raise ValueError("当前库存不支持业务日期筛选")
        if self.view == "movement" and self.warning is not None:
            raise ValueError("期间变动不支持库存预警筛选")
        return self


class StockReportDimensions(BaseModel):
    """仓库与商品组合为稳定行身份，档案描述取当前值，不伪造历史快照。"""

    id: str
    warehouse_name: str
    goods_code: str
    goods_name: str
    spec: str | None
    unit: str


class StockBalanceReportOut(StockReportDimensions):
    """已建账库存余额，数量和金额为当前状态，不生成未建账组合。"""

    quantity: Quantity
    avg_cost: UnitCost
    stock_amount: Money
    warning: StockWarning


class StockMovementReportOut(StockReportDimensions):
    """包含确认和反向流水的期间变动，不将净变动称为期末结存。"""

    in_quantity: Quantity
    out_quantity: Quantity
    net_quantity: Quantity
    in_amount: Money
    out_amount: Money
    net_amount: Money


class StockBalanceReportSummary(BaseModel):
    """完整筛选余额的金额和去重商品数，不跨单位合计数量。"""

    goods_count: int
    stock_amount: Money


class StockMovementReportSummary(BaseModel):
    """完整筛选流水的带方向成本变动，商品跨仓库只计一次。"""

    goods_count: int
    in_amount: Money
    out_amount: Money
    net_amount: Money


class StockReportExport(BaseModel):
    """导出复用报表视图与筛选，按服务端字段白名单生成文件。"""

    model_config = ConfigDict(extra="forbid")
    query: StockReportQuery = Field(default_factory=StockReportQuery)
    fields: list[str] = Field(min_length=1, max_length=30)
    format: Literal["xlsx", "csv"] = "xlsx"
    sheet_name: str = Field(default="库存报表", max_length=31)
    filename: str | None = Field(default=None, max_length=200)

    @field_validator("fields")
    @classmethod
    def unique_fields(cls, value: list[str]) -> list[str]:
        """保持选择顺序并去重，字段是否适用由实际视图决定。"""
        return list(dict.fromkeys(value))

    @field_validator("filename", "sheet_name")
    @classmethod
    def safe_filename(cls, value: str | None) -> str | None:
        """拒绝路径、控制字符以及文件与工作表非法字符。"""
        if value is None:
            return None
        value = value.strip()
        if value in {".", ".."} or any(ord(char) < 32 or char in '<>:"/\\|?*[]' for char in value):
            raise ValueError("文件名或工作表名包含非法字符")
        return value

    def download_name(self) -> str:
        """空文件名采用库存报表加北京时间戳，扩展名跟随实际格式。"""
        default = f"库存报表_{datetime.now(timezone(timedelta(hours=8))):%Y%m%d_%H%M%S}"
        base = re.sub(r"\.(xlsx|csv)$", "", self.filename or default, flags=re.I) or default
        return f"{base}.{self.format}"

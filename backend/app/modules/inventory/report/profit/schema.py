import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator

Money = Annotated[Decimal, PlainSerializer(lambda value: format(value, ".2f"), return_type=str, when_used="json-unless-none")]


class ProfitReportQuery(BaseModel):
    """毛利报表按当前有效业务查询，日期以每类单据自身业务日期为准。"""

    view: Literal["documents", "goods"] = "documents"
    business_date: list[date] | None = Field(default=None, min_length=2, max_length=2)
    business_no: str | None = Field(default=None, max_length=64)
    customer_name: str | None = Field(default=None, max_length=200)
    warehouse_id: int | None = Field(default=None, gt=0)
    warehouse_name: str | None = Field(default=None, max_length=100)
    category_id: int | None = Field(default=None, gt=0)
    category_name: str | None = Field(default=None, max_length=100)
    goods_code: str | None = Field(default=None, max_length=64)
    goods_name: str | None = Field(default=None, max_length=200)

    @field_validator("business_no", "customer_name", "warehouse_name", "category_name", "goods_code", "goods_name")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        """空输入不产生名称筛选，模糊匹配的通配字符由查询层转义。"""
        return value.strip() or None if value is not None else None

    @field_validator("business_date")
    @classmethod
    def ordered_dates(cls, value: list[date] | None) -> list[date] | None:
        """拒绝逆序日期，保持分页、完整汇总和导出条件一致。"""
        if value and value[0] > value[1]:
            raise ValueError("业务日期必须按起止顺序传入")
        return value

    @model_validator(mode="after")
    def validate_view_filters(self) -> Self:
        """商品汇总不隐式接受只用于单据明细的单号条件。"""
        if self.view == "goods" and self.business_no:
            raise ValueError("商品汇总不支持来源单号筛选")
        return self


class ProfitReportSource(BaseModel):
    """原销售出库或退货来源，详情仍需独立业务权限及数据范围。"""

    business_type: Literal["sale_out", "sale_return"]
    business_id: int


class ProfitReportAmounts(BaseModel):
    """净收入与成本允许为负，毛利率为百分数而不是比例小数。"""

    id: str
    warehouse_name: str
    net_sale_amount: Money
    net_cost_amount: Money
    gross_profit: Money
    gross_margin: Money | None


class ProfitDocumentReportOut(ProfitReportAmounts):
    """有效出库和退货各一行，退货同时冲减收入和固化成本。"""

    business_no: str
    business_date: date
    customer_name: str
    source: ProfitReportSource


class ProfitGoodsReportOut(ProfitReportAmounts):
    """按商品、仓库及完整快照分组，不跨规格和单位合并。"""

    goods_code: str
    goods_name: str
    spec: str | None
    unit: str


class ProfitReportSummary(BaseModel):
    """完整筛选金额计算汇总毛利率，不对各行百分比取平均。"""

    net_sale_amount: Money
    net_cost_amount: Money
    gross_profit: Money
    gross_margin: Money | None


class ProfitReportExport(BaseModel):
    """全量导出使用相同业务查询，格式、字段和文件名由服务端校验。"""

    model_config = ConfigDict(extra="forbid")
    query: ProfitReportQuery = Field(default_factory=ProfitReportQuery)
    fields: list[str] = Field(min_length=1, max_length=30)
    format: Literal["xlsx", "csv"] = "xlsx"
    sheet_name: str = Field(default="毛利报表", max_length=31)
    filename: str | None = Field(default=None, max_length=200)

    @field_validator("fields")
    @classmethod
    def unique_fields(cls, value: list[str]) -> list[str]:
        """保持用户字段顺序并去重，白名单按实际视图校验。"""
        return list(dict.fromkeys(value))

    @field_validator("filename", "sheet_name")
    @classmethod
    def safe_filename(cls, value: str | None) -> str | None:
        """拒绝路径、控制字符以及文件和工作表非法字符。"""
        if value is None:
            return None
        value = value.strip()
        if value in {".", ".."} or any(ord(char) < 32 or char in '<>:"/\\|?*[]' for char in value):
            raise ValueError("文件名或工作表名包含非法字符")
        return value

    def download_name(self) -> str:
        """空文件名默认毛利报表加本地时间戳，扩展名与导出格式一致。"""
        default_name = f"毛利报表_{datetime.now(timezone(timedelta(hours=8))):%Y%m%d_%H%M%S}"
        base = re.sub(r"\.(xlsx|csv)$", "", self.filename or default_name, flags=re.I) or default_name
        return f"{base}.{self.format}"

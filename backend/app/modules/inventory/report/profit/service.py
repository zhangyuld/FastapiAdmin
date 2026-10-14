import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.utils.excel_util import ExcelUtil

from .crud import ProfitReportCRUD
from .schema import ProfitDocumentReportOut, ProfitGoodsReportOut, ProfitReportExport, ProfitReportQuery, ProfitReportSummary

AMOUNT_COLUMNS = {"net_sale_amount": "净销售金额", "net_cost_amount": "净销售成本", "gross_profit": "毛利", "gross_margin": "毛利率"}
DOCUMENT_COLUMNS = {"business_no": "来源单号", "business_date": "业务日期", "customer_name": "客户", "warehouse_name": "仓库", **AMOUNT_COLUMNS}
GOODS_COLUMNS = {"goods_code": "商品编码", "goods_name": "商品名称", "spec": "规格", "unit": "单位", "warehouse_name": "仓库", **AMOUNT_COLUMNS}
TEXT_FIELDS = {"business_no", "customer_name", "warehouse_name", "goods_code", "goods_name", "spec", "unit"}


def profit_metrics(sale: Decimal, cost: Decimal) -> dict[str, Decimal | None]:
    """完整金额计算毛利与百分数，非正净收入不生成误导性比例。"""
    with localcontext() as context:
        context.prec = max(60, len(sale.as_tuple().digits) + len(cost.as_tuple().digits) + 10)
        profit = sale - cost
        margin = (profit / sale * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if sale > 0 else None
        if margin == 0:
            margin = Decimal("0.00")
        return {"net_sale_amount": sale, "net_cost_amount": cost, "gross_profit": profit, "gross_margin": margin}


def safe_export_value(field: str, value: object) -> object:
    """档案文本防止被当作公式，服务端生成的金额及百分数保持原样。"""
    if field in TEXT_FIELDS and isinstance(value, str) and (value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))):
        return "'" + value
    return value


class ProfitReportService:
    """毛利只读业务，不修改销售状态、固化成本、库存或应收。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """功能权限由控制器独立校验，原单详情不继承报表授权。"""
        self.auth = auth
        self.crud = ProfitReportCRUD(db)

    @staticmethod
    def _serialize(row: dict[str, Any], view: str) -> ProfitDocumentReportOut | ProfitGoodsReportOut:
        """响应毛利率用 Decimal 计算，稳定分组身份不依赖分页位置。"""
        values = {**row, **profit_metrics(row["net_sale_amount"], row["net_cost_amount"])}
        if view == "documents":
            values["source"] = {"business_type": row["business_type"], "business_id": row["business_id"]}
            return ProfitDocumentReportOut.model_validate(values)
        identity = [row[key] for key in ("goods_id", "warehouse_id", "goods_code", "goods_name", "spec", "unit")]
        values["id"] = "goods:" + hashlib.sha256(json.dumps(identity, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
        return ProfitGoodsReportOut.model_validate(values)

    async def page(self, query: ProfitReportQuery, page_no: int, page_size: int, order_by: list[dict[str, str]] | None = None) -> PageResultSchema[ProfitDocumentReportOut | ProfitGoodsReportOut]:
        """缺失成本不输出部分页，列表金额与毛利率固定两位字符串。"""
        rows, total = await self.crud.rows(query, page_no, page_size, order_by)
        return PageResultSchema(page_no=page_no, page_size=page_size, total=total, has_next=page_no * page_size < total, items=[self._serialize(row, query.view) for row in rows])

    async def summary(self, query: ProfitReportQuery) -> ProfitReportSummary:
        """汇总比例按完整净收入与成本重算，不平均分页或明细毛利率。"""
        row = await self.crud.summary(query)
        return ProfitReportSummary.model_validate(profit_metrics(row["net_sale_amount"], row["net_cost_amount"]))

    async def export(self, data: ProfitReportExport) -> bytes:
        """按所选字段顺序输出完整筛选，毛利率显示百分号或不可计算占位。"""
        columns = DOCUMENT_COLUMNS if data.query.view == "documents" else GOODS_COLUMNS
        if not set(data.fields).issubset(columns):
            raise CustomException(msg="导出包含当前视图不支持的字段", status_code=422)
        rows, total = await self.crud.rows(data.query, page_no=1, page_size=100001)
        if total > 100000:
            raise CustomException(msg="导出超过10万行，请缩小筛选范围", status_code=422)
        values = []
        for row in rows:
            value = self._serialize(row, data.query.view).model_dump(mode="json")
            value["gross_margin"] = value["gross_margin"] + "%" if value["gross_margin"] is not None else "—"
            if value.get("spec") is None:
                value["spec"] = "—"
            values.append({field: safe_export_value(field, item) for field, item in value.items()})
        mapping = {field: columns[field] for field in data.fields}
        if data.format == "csv":
            return await ExcelUtil.aexport_list2csv(list_data=values, mapping_dict=mapping)
        return await ExcelUtil.aexport_list2excel(list_data=values, mapping_dict=mapping, sheet_name=data.sheet_name or "毛利报表")

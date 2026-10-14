import hashlib
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.utils.excel_util import ExcelUtil

from .crud import SaleReportCRUD
from .schema import SaleDocumentReportOut, SaleGoodsReportOut, SaleReportExport, SaleReportQuery, SaleReportSummary

AMOUNT_COLUMNS = {"sale_amount": "销售金额", "return_amount": "退货金额", "net_sale_amount": "净销售金额"}
DOCUMENT_COLUMNS = {"business_no": "来源单号", "business_date": "业务日期", "customer_name": "客户", "warehouse_name": "仓库", **AMOUNT_COLUMNS}
GOODS_COLUMNS = {
    "goods_code": "商品编码",
    "goods_name": "商品名称",
    "spec": "规格",
    "unit": "单位",
    "warehouse_name": "仓库",
    "sale_quantity": "销售数量",
    "return_quantity": "退货数量",
    "net_quantity": "净销售数量",
    **AMOUNT_COLUMNS,
}

TEXT_FIELDS = {"business_no", "customer_name", "warehouse_name", "goods_code", "goods_name", "spec", "unit"}


def safe_export_value(field: str, value: object) -> object:
    """档案文本避免电子表格公式执行，金额和数量保持原有方向及精度。"""
    if field in TEXT_FIELDS and isinstance(value, str) and (value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))):
        return "'" + value
    return value


class SaleReportService:
    """销售报表只读业务，不修改销售状态、库存或应收，不维护报表表。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """功能权限在控制器验证，来源详情不继承报表授权。"""
        self.auth = auth
        self.crud = SaleReportCRUD(db)

    @staticmethod
    def _serialize(row: dict, view: str) -> SaleDocumentReportOut | SaleGoodsReportOut:
        """单据键区分业务类型，商品键覆盖完整分组快照且不依赖分页序号。"""
        values = dict(row)
        if view == "documents":
            values["source"] = {"business_type": row["business_type"], "business_id": row["business_id"]}
            return SaleDocumentReportOut.model_validate(values)
        identity = [row[key] for key in ("goods_id", "warehouse_id", "goods_code", "goods_name", "spec", "unit")]
        values["id"] = "goods:" + hashlib.sha256(json.dumps(identity, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
        return SaleGoodsReportOut.model_validate(values)

    async def page(self, query: SaleReportQuery, page_no: int, page_size: int, order_by: list | None = None) -> PageResultSchema[SaleDocumentReportOut | SaleGoodsReportOut]:
        """分组分页响应保持金额两位、数量三位，来源仅在单据视图返回。"""
        rows, total = await self.crud.rows(query, page_no, page_size, order_by)
        return PageResultSchema(page_no=page_no, page_size=page_size, total=total, has_next=page_no * page_size < total, items=[self._serialize(row, query.view) for row in rows])

    async def summary(self, query: SaleReportQuery) -> SaleReportSummary:
        """返回全部筛选有效业务的金额与去重单据数，不使用当前页合计。"""
        return SaleReportSummary.model_validate(await self.crud.summary(query))

    async def export(self, data: SaleReportExport) -> bytes:
        """导出复用有效明细筛选，非法字段或超限结果不生成部分文件。"""
        columns = DOCUMENT_COLUMNS if data.query.view == "documents" else GOODS_COLUMNS
        if not set(data.fields).issubset(columns):
            raise CustomException(msg="导出包含当前视图不支持的字段", status_code=422)
        rows, total = await self.crud.rows(data.query, page_no=1, page_size=100001)
        if total > 100000:
            raise CustomException(msg="导出超过10万行，请缩小筛选范围", status_code=422)
        values = [{field: safe_export_value(field, value) for field, value in self._serialize(row, data.query.view).model_dump(mode="json").items()} for row in rows]
        mapping = {field: columns[field] for field in data.fields}
        if data.format == "csv":
            return await ExcelUtil.aexport_list2csv(list_data=values, mapping_dict=mapping)
        return await ExcelUtil.aexport_list2excel(list_data=values, mapping_dict=mapping, sheet_name=data.sheet_name or "销售报表")

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.utils.excel_util import ExcelUtil

from .crud import StockReportCRUD
from .schema import StockBalanceReportOut, StockBalanceReportSummary, StockMovementReportOut, StockMovementReportSummary, StockReportExport, StockReportQuery

DIMENSION_COLUMNS = {"goods_code": "商品编码", "goods_name": "商品名称", "spec": "规格", "unit": "单位", "warehouse_name": "仓库"}
BALANCE_COLUMNS = {**DIMENSION_COLUMNS, "quantity": "库存数量", "avg_cost": "平均成本", "stock_amount": "库存金额", "warning": "预警"}
MOVEMENT_COLUMNS = {
    **DIMENSION_COLUMNS,
    "in_quantity": "入库数量",
    "out_quantity": "出库数量",
    "net_quantity": "净变动数量",
    "in_amount": "入库金额",
    "out_amount": "出库金额",
    "net_amount": "净变动金额",
}
WARNING_LABELS = {"normal": "正常", "low": "低于下限", "high": "高于上限"}


def safe_export_value(field: str, value: object) -> object:
    """档案文本避免被电子表格执行为公式，成本金额和带方向数量保持精度。"""
    if field in DIMENSION_COLUMNS and isinstance(value, str) and (value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))):
        return "'" + value
    return value


class StockReportService:
    """库存报表只读余额与流水，不修改库存、成本或来源单据状态。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """控制器独立校验报表权限，统计不继承其他库存接口的授权。"""
        self.auth = auth
        self.crud = StockReportCRUD(db)

    @staticmethod
    def _serialize(row: dict[str, Any], view: str) -> StockBalanceReportOut | StockMovementReportOut:
        """仓库商品键跨分页稳定，不为聚合结果伪造来源单据。"""
        values = {**row, "id": f"{view}:{row['warehouse_id']}:{row['goods_id']}"}
        model = StockBalanceReportOut if view == "balance" else StockMovementReportOut
        return model.model_validate(values)

    async def page(self, query: StockReportQuery, page_no: int, page_size: int, order_by: list[dict[str, str]] | None = None) -> PageResultSchema[StockBalanceReportOut | StockMovementReportOut]:
        """返回当前视图分页，保持金额两位、数量三位、平均成本四位。"""
        rows, total = await self.crud.rows(query, page_no, page_size, order_by)
        return PageResultSchema(page_no=page_no, page_size=page_size, total=total, has_next=page_no * page_size < total, items=[self._serialize(row, query.view) for row in rows])

    async def summary(self, query: StockReportQuery) -> StockBalanceReportSummary | StockMovementReportSummary:
        """返回整个筛选结果金额和去重商品数，不采用当前页或浮点数求总量。"""
        model = StockBalanceReportSummary if query.view == "balance" else StockMovementReportSummary
        return model.model_validate(await self.crud.summary(query))

    async def export(self, data: StockReportExport) -> bytes:
        """按视图字段与用户顺序生成完整文件，超限明确拒绝而不静默截断。"""
        columns = BALANCE_COLUMNS if data.query.view == "balance" else MOVEMENT_COLUMNS
        if not set(data.fields).issubset(columns):
            raise CustomException(msg="导出包含当前视图不支持的字段", status_code=422)
        rows, total = await self.crud.rows(data.query, page_no=1, page_size=100001)
        if total > 100000:
            raise CustomException(msg="导出超过10万行，请缩小筛选范围", status_code=422)
        values = []
        for row in rows:
            value = self._serialize(row, data.query.view).model_dump(mode="json")
            if data.query.view == "balance":
                value["warning"] = WARNING_LABELS[value["warning"]]
            values.append({field: safe_export_value(field, item) for field, item in value.items()})
        mapping = {field: columns[field] for field in data.fields}
        if data.format == "csv":
            return await ExcelUtil.aexport_list2csv(list_data=values, mapping_dict=mapping)
        return await ExcelUtil.aexport_list2excel(list_data=values, mapping_dict=mapping, sheet_name=data.sheet_name or "库存报表")

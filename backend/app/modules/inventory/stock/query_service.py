from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException

from .export import export_rows
from .query_crud import StockQueryCRUD
from .query_schema import BalanceExport, BalanceOut, BalanceQuery, LogExport, LogOut, LogQuery

BALANCE_COLUMNS = {
    "goods_code": "商品编码",
    "goods_name": "商品名称",
    "warehouse_name": "仓库",
    "spec": "规格",
    "unit": "单位",
    "quantity": "库存数量",
    "avg_cost": "平均成本",
    "stock_amount": "库存金额",
    "warning": "库存预警",
    "last_business_time": "最近变动时间",
}
LOG_COLUMNS = {
    "goods_code": "商品编码",
    "goods_name": "商品名称",
    "warehouse_name": "仓库",
    "business_type": "业务类型",
    "operation_type": "操作类型",
    "business_no": "来源单号",
    "business_date": "业务日期",
    "before_quantity": "变动前数量",
    "change_quantity": "变动数量",
    "after_quantity": "变动后数量",
    "unit_cost": "单位成本",
    "cost_amount": "成本金额",
    "posted_time": "入账时间",
    "created_name": "操作人",
    "remark": "备注",
}
BUSINESS_LABELS = {
    "purchase_in": "采购入库",
    "purchase_return": "采购退货",
    "sale_out": "销售出库",
    "sale_return": "销售退货",
    "opening_balance": "期初库存",
    "stock_check_gain": "盘盈",
    "stock_check_loss": "盘亏",
}


class StockQueryService:
    """库存只读查询、详情和字段白名单导出。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession, kind: Literal["balance", "log"]) -> None:
        """绑定模块内只读访问模型和响应类型。"""
        self.crud = StockQueryCRUD(auth, db, kind)
        self.kind = kind
        self.output = BalanceOut if kind == "balance" else LogOut

    async def page(self, page_no: int, page_size: int, search: BalanceQuery | LogQuery, order_by: list[dict[str, str]] | None = None) -> PageResultSchema:
        """与导出共用筛选，分页仅加载当前页。"""
        rows, total = await self.crud.rows(search, page_no, page_size, order_by=order_by)
        return PageResultSchema(page_no=page_no, page_size=page_size, total=total, has_next=page_no * page_size < total, items=[self.output.model_validate(row) for row in rows])

    async def detail(self, id: int) -> BalanceOut | LogOut:
        """按只读模型查询，缺失记录返回 404。"""
        rows, _ = await self.crud.rows(BalanceQuery() if self.kind == "balance" else LogQuery(), id=id)
        if not rows:
            raise CustomException(msg="库存记录不存在", status_code=404)
        return self.output.model_validate(rows[0])

    async def export(self, data: BalanceExport | LogExport) -> bytes:
        """只导出请求指定的合法字段，金额保持固定小数字符串。"""
        rows, _ = await self.crud.rows(data.query)
        values = []
        for row in rows:
            value = self.output.model_validate(row).model_dump(mode="json")
            value["created_name"] = value.get("created_by", {}).get("name", "") if value.get("created_by") else ""
            if self.kind == "balance":
                value["warning"] = {"low": "低于下限", "high": "高于上限", "normal": "正常"}.get(value["warning"], value["warning"])
            else:
                value["business_type"] = BUSINESS_LABELS.get(value["business_type"], value["business_type"])
                value["operation_type"] = {"confirm": "确认", "void": "冲销"}.get(value["operation_type"], value["operation_type"])
            values.append(value)
        return await export_rows(values, data, BALANCE_COLUMNS if self.kind == "balance" else LOG_COLUMNS)

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.utils.excel_util import ExcelUtil

from .query_crud import FinanceQueryCRUD
from .query_schema import BalanceExport, BalanceOut, BalanceQuery, BillDetail, BillExport, BillOut, BillQuery, ExportOptions, FinanceKind, SummaryOut

BILL_COLUMNS = {
    "party_code": "对象编码",
    "party_name": "往来对象",
    "business_no": "来源单号",
    "business_type": "业务类型",
    "operation_type": "操作类型",
    "amount": "变动金额",
    "allocated_amount": "已核销金额",
    "unallocated_amount": "未核销金额",
    "bill_date": "账单日期",
    "status": "核销状态",
    "reversal_state": "冲销状态",
    "reversal_id": "原账单ID",
    "created_name": "记账人",
    "created_time": "记账时间",
    "remark": "备注",
}
BALANCE_COLUMNS = {
    "party_code": "对象编码",
    "party_name": "往来对象",
    "business_net_amount": "业务净额",
    "allocated_net_amount": "已核销净额",
    "unsettled_net_amount": "未核销净额",
    "bill_count": "账单数",
}
BUSINESS_LABELS = {"sale_out": "销售出库", "sale_return": "销售退货", "purchase_in": "采购入库", "purchase_return": "采购退货"}


class FinanceQueryService:
    """往来账单及余额只读业务，不改变采购销售记账和资金核销字段。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession, kind: FinanceKind) -> None:
        """财务功能权限在控制器验证，来源详情由对应业务接口独立授权。"""
        self.auth, self.kind = auth, kind
        self.crud = FinanceQueryCRUD(db, kind)

    async def page(self, page_no: int, page_size: int, query: BillQuery, order_by: list | None = None) -> PageResultSchema:
        """返回当前页账单，金额保持定点数格式。"""
        rows, total = await self.crud.bills(query, page_no, page_size, order_by=order_by)
        return PageResultSchema(page_no=page_no, page_size=page_size, total=total, has_next=page_no * page_size < total, items=[BillOut.model_validate(row) for row in rows])

    async def detail(self, id: int) -> BillDetail:
        """读取账单和原账单/冲销账单，缺失记录返回 404。"""
        rows, _ = await self.crud.bills(BillQuery(), id=id)
        if not rows:
            raise CustomException(msg="往来账单不存在", status_code=404)
        row = rows[0]
        related, _ = await self.crud.bills(BillQuery(), related_to=row["reversal_id"] or id)
        return BillDetail(**BillOut.model_validate(row).model_dump(), related_bills=[BillOut.model_validate(value) for value in related if value["id"] != id])

    async def balance_page(self, page_no: int, page_size: int, query: BalanceQuery, order_by: list | None = None) -> PageResultSchema:
        """分页按往来对象汇总，原单和反向单均参与有方向计算。"""
        rows, total = await self.crud.balances(query, page_no, page_size, order_by)
        return PageResultSchema(page_no=page_no, page_size=page_size, total=total, has_next=page_no * page_size < total, items=[BalanceOut.model_validate(row) for row in rows])

    async def summary(self, query: BalanceQuery) -> SummaryOut:
        """汇总当前余额视图全部对象，不受当前页大小影响。"""
        return SummaryOut.model_validate(await self.crud.summary(query))

    async def export(self, data: BillExport | BalanceExport) -> bytes:
        """按合法字段及用户顺序导出全部筛选结果，与前端导出标签一致。"""
        is_balance = isinstance(data, BalanceExport)
        rows, _ = await self.crud.balances(data.query) if is_balance else await self.crud.bills(data.query)
        values = []
        for row in rows:
            value = (BalanceOut if is_balance else BillOut).model_validate(row).model_dump(mode="json")
            if not is_balance:
                value["created_name"] = value["created_by"]["name"] if value.get("created_by") else ""
                value["business_type"] = BUSINESS_LABELS.get(value["business_type"], value["business_type"])
                value["operation_type"] = {"confirm": "确认", "void": "冲销"}[value["operation_type"]]
                value["status"] = ["未结清", "部分结清", "已结清"][value["status"]]
                value["reversal_state"] = {"original": "未冲销", "reversed": "已冲销", "reversal": "反向账单"}[value["reversal_state"]]
            values.append(value)
        columns = dict(BALANCE_COLUMNS if is_balance else BILL_COLUMNS)
        party_label = "客户" if self.kind == "receivable" else "供应商"
        columns.update(party_code=party_label + "编码", party_name=party_label + "名称")
        return await self._export_rows(values, data, columns)

    @staticmethod
    async def _export_rows(rows: list[dict], data: ExportOptions, columns: dict[str, str]) -> bytes:
        """模块内复用框架文件生成器，不依赖库存模块的私有导出工具。"""
        if not set(data.fields).issubset(columns):
            raise CustomException(msg="导出包含不支持的字段", status_code=422)
        mapping = {field: columns[field] for field in data.fields}
        if data.format == "csv":
            return await ExcelUtil.aexport_list2csv(list_data=rows, mapping_dict=mapping)
        return await ExcelUtil.aexport_list2excel(list_data=rows, mapping_dict=mapping, sheet_name=data.sheet_name or "往来")

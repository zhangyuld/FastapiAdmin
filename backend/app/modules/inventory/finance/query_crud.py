from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.core.exceptions import CustomException
from app.modules.inventory.basic.model import CustomerModel, SupplierModel

from .model import PayableModel, ReceivableModel
from .query_schema import BalanceQuery, BillQuery, FinanceKind, PartyQuery


class FinanceQueryCRUD:
    """独立财务查询授权的共享往来数据，不以记账人拆分客户或供应商余额。"""

    def __init__(self, db: AsyncSession, kind: FinanceKind) -> None:
        """绑定应收或应付账单及往来对象，不提供通用写入方法。"""
        self.db, self.kind = db, kind
        self.model = ReceivableModel if kind == "receivable" else PayableModel
        self.party = CustomerModel if kind == "receivable" else SupplierModel
        prefix = "customer" if kind == "receivable" else "supplier"
        self.party_id = getattr(self.model, prefix + "_id")
        self.code = getattr(self.party, prefix + "_code")
        self.name = getattr(self.party, prefix + "_name")

    def _conditions(self, query: PartyQuery) -> list[Any]:
        """保留停用对象历史账单，只排除已删除账单。"""
        conditions = [self.model.is_deleted.is_(False)]
        if query.party_id is not None:
            conditions.append(self.party_id == query.party_id)
        for value, column in ((query.party_code, self.code), (query.party_name, self.name)):
            if value and value.strip():
                conditions.append(column.contains(value.strip(), autoescape=True))
        return conditions

    def _reversed(self) -> Any:
        """冲销状态按账单关联推导，不覆盖原核销状态。"""
        reverse = aliased(self.model)
        return select(reverse.id).where(reverse.reversal_id == self.model.id, reverse.is_deleted.is_(False)).exists()

    @staticmethod
    def _order(order_by: list | None, columns: dict[str, Any], default: str) -> list[Any]:
        """只允许明确字段和方向，拒绝格式异常和任意 SQL 排序。"""
        result = []
        for mapping in order_by or [{default: "desc"}]:
            if not isinstance(mapping, dict):
                raise CustomException(msg="排序格式无效", status_code=422)
            for field, direction in mapping.items():
                if field not in columns or not isinstance(direction, str) or direction.lower() not in {"asc", "desc"}:
                    raise CustomException(msg="排序字段或方向无效", status_code=422)
                result.append(columns[field].asc() if direction.lower() == "asc" else columns[field].desc())
        return result

    async def bills(
        self, query: BillQuery, page_no: int | None = None, page_size: int = 10, id: int | None = None, related_to: int | None = None, order_by: list | None = None
    ) -> tuple[list[dict], int]:
        """账单分页与全量导出共用筛选，详情额外读取原账单及冲销记录。"""
        model = self.model
        conditions = self._conditions(query)
        for field in ("business_type", "operation_type", "status", "created_id", "updated_id"):
            value = getattr(query, field)
            if value is not None:
                conditions.append(getattr(model, field) == value)
        if query.business_no and query.business_no.strip():
            conditions.append(model.business_no.contains(query.business_no.strip(), autoescape=True))
        for field in ("bill_date", "created_time", "updated_time"):
            values = getattr(query, field)
            if values:
                conditions.append(getattr(model, field).between(*values))
        reversed_exists = self._reversed()
        if query.reversal_state == "reversal":
            conditions.append(model.reversal_id.is_not(None))
        elif query.reversal_state == "reversed":
            conditions.extend([model.reversal_id.is_(None), reversed_exists])
        elif query.reversal_state == "original":
            conditions.extend([model.reversal_id.is_(None), ~reversed_exists])
        if id is not None:
            conditions.append(model.id == id)
        if related_to is not None:
            conditions.append((model.id == related_to) | (model.reversal_id == related_to))
        statement = select(model, self.code, self.name, reversed_exists.label("has_reversal")).join(self.party, self.party.id == self.party_id).where(*conditions)
        total = await self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        columns = {col.key: getattr(model, col.key) for col in model.__table__.columns}
        columns.update(party_name=self.name, party_code=self.code)
        statement = statement.order_by(*self._order(order_by, columns, "id"), model.id.desc()).options(selectinload(model.created_by), selectinload(model.updated_by))
        if page_no is not None:
            statement = statement.offset((page_no - 1) * page_size).limit(page_size)
        rows = []
        for bill, code, name, has_reversal in (await self.db.execute(statement)).all():
            values = {col.key: getattr(bill, col.key) for col in model.__table__.columns}
            values.update(
                party_id=getattr(bill, "customer_id" if self.kind == "receivable" else "supplier_id"),
                party_code=code,
                party_name=name,
                created_by=bill.created_by,
                updated_by=bill.updated_by,
                reversal_state="reversal" if bill.reversal_id is not None else "reversed" if has_reversal else "original",
            )
            rows.append(values)
        return rows, total

    def _balances(self, query: BalanceQuery) -> Any:
        """先按对象计算有方向净额，再按余额符号过滤，不把退货重复扣减。"""
        model = self.model
        net = func.sum(model.amount)
        unsettled = func.sum(case((model.amount < 0, -model.unallocated_amount), else_=model.unallocated_amount))
        statement = (
            select(
                self.party_id.label("id"),
                self.party_id.label("party_id"),
                self.code.label("party_code"),
                self.name.label("party_name"),
                net.label("business_net_amount"),
                (net - unsettled).label("allocated_net_amount"),
                unsettled.label("unsettled_net_amount"),
                func.count(model.id).label("bill_count"),
            )
            .join(self.party, self.party.id == self.party_id)
            .where(*self._conditions(query))
            .group_by(self.party_id, self.code, self.name)
        )
        if query.balance_state:
            predicate = unsettled > 0 if query.balance_state == "positive" else unsettled < 0 if query.balance_state == "negative" else unsettled == 0
            statement = statement.having(predicate)
        return statement.subquery()

    async def balances(self, query: BalanceQuery, page_no: int | None = None, page_size: int = 10, order_by: list | None = None) -> tuple[list[dict], int]:
        """仅查询已有账单的往来对象，汇总不受账单分页影响。"""
        grouped = self._balances(query)
        total = await self.db.scalar(select(func.count()).select_from(grouped)) or 0
        columns = {col.key: col for col in grouped.c}
        statement = select(grouped).order_by(*self._order(order_by, columns, "id"), grouped.c.id.desc())
        if page_no is not None:
            statement = statement.offset((page_no - 1) * page_size).limit(page_size)
        return [dict(row) for row in (await self.db.execute(statement)).mappings().all()], total

    async def summary(self, query: BalanceQuery) -> dict:
        """正向未核销余额和负向冲减余额分别汇总，避免跨对象抵消待收待付。"""
        grouped = self._balances(query)
        net = grouped.c.unsettled_net_amount
        statement = select(
            func.count().label("party_count"),
            func.coalesce(func.sum(grouped.c.business_net_amount), 0).label("business_net_amount"),
            func.coalesce(func.sum(net), 0).label("unsettled_net_amount"),
            func.coalesce(func.sum(case((net > 0, net), else_=0)), 0).label("positive_balance"),
            func.coalesce(func.sum(case((net < 0, -net), else_=0)), 0).label("negative_balance"),
        ).select_from(grouped)
        return dict((await self.db.execute(statement)).mappings().one())

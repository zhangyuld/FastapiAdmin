from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, TypedDict

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.modules.inventory.basic.model import CustomerModel, GoodsModel, WarehouseModel
from app.modules.inventory.enums import DocumentStatus, EnableStatus
from app.modules.system.user.model import UserModel

from ..model import SaleOutModel, SaleReturnItemModel, SaleReturnModel
from .schema import SaleReturnCreateSchema, SaleReturnUpdateSchema


class SaleReturnItemValues(TypedDict):
    """后端核对来源并计算后的退货快照。"""

    line_no: int
    source_sale_out_item_id: int
    goods_id: int
    goods_code: str
    goods_name: str
    spec: str | None
    unit: str
    quantity: Decimal
    unit_price: Decimal
    line_amount: Decimal
    unit_cost: Decimal
    cost_amount: Decimal


@dataclass
class ReturnedTotals:
    """同一来源明细已确认且未作废的数量、金额和成本。"""

    quantity: Decimal = Decimal("0.000")
    amount: Decimal = Decimal("0.00")
    cost: Decimal = Decimal("0.00")


@dataclass
class SaleReturnNames:
    """历史名称和来源单号批量映射。"""

    customers: dict[int, str]
    warehouses: dict[int, str]
    users: dict[int, str]
    sources: dict[int, str]


class SaleReturnCRUD(CRUDBase[SaleReturnModel, SaleReturnCreateSchema, SaleReturnUpdateSchema]):
    """原单退货数据层，单据按数据范围隔离，所有写入只 flush。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """初始化退货数据权限上下文。"""
        super().__init__(model=SaleReturnModel, auth=auth, db=db)

    async def _build_conditions(self, include_deleted: bool = False, **kwargs: Any) -> list[ColumnElement]:
        """来源单号通过子查询筛选，不破坏主单数据权限和分页计数。"""
        source_order_no = kwargs.pop("source_order_no", None)
        conditions = await super()._build_conditions(include_deleted=include_deleted, **kwargs)
        if source_order_no:
            keyword = source_order_no[1] if isinstance(source_order_no, tuple) else source_order_no
            conditions.append(self.model.source_sale_out_id.in_(select(SaleOutModel.id).where(SaleOutModel.order_no.like(f"%{keyword}%"))))
        return conditions

    async def get_document(self, id: int, *, lock: bool = False) -> SaleReturnModel | None:
        """锁定时仅锁主单，审计用户单独加载，刷新旧 ORM 缓存。"""
        conditions = await self._build_conditions(id=id)
        options = [selectinload(self.model.created_by), selectinload(self.model.updated_by)] if lock else self._loader_options()
        statement = select(self.model).where(*conditions).options(*options).execution_options(populate_existing=True)
        if lock:
            statement = statement.with_for_update(of=self.model)
        return (await self.db.execute(statement)).scalars().first()

    async def get_items(self, id: int, *, lock: bool = False) -> Sequence[SaleReturnItemModel]:
        """主单授权后读取有效退货行。"""
        statement = (
            select(SaleReturnItemModel)
            .where(
                SaleReturnItemModel.sale_return_id == id,
                SaleReturnItemModel.is_deleted.is_(False),
            )
            .order_by(SaleReturnItemModel.line_no)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        return (await self.db.execute(statement)).scalars().all()

    async def get_name_maps(self, documents: Sequence[SaleReturnModel]) -> SaleReturnNames:
        """批量补名称，历史单据不受档案停用及删除影响。"""
        customer_ids = {row.customer_id for row in documents}
        warehouse_ids = {row.warehouse_id for row in documents}
        user_ids = {id for row in documents for id in (row.confirmed_id, row.voided_id) if id is not None}
        source_ids = {row.source_sale_out_id for row in documents if row.source_sale_out_id is not None}
        customers = dict((await self.db.execute(select(CustomerModel.id, CustomerModel.customer_name).where(CustomerModel.id.in_(customer_ids)))).all()) if customer_ids else {}
        warehouses = dict((await self.db.execute(select(WarehouseModel.id, WarehouseModel.warehouse_name).where(WarehouseModel.id.in_(warehouse_ids)))).all()) if warehouse_ids else {}
        users = dict((await self.db.execute(select(UserModel.id, UserModel.name).where(UserModel.id.in_(user_ids)))).all()) if user_ids else {}
        sources = dict((await self.db.execute(select(SaleOutModel.id, SaleOutModel.order_no).where(SaleOutModel.id.in_(source_ids)))).all()) if source_ids else {}
        return SaleReturnNames(customers, warehouses, users, sources)

    async def validate_archives(self, customer_id: int, warehouse_id: int, goods_ids: set[int]) -> None:
        """共享锁当前读取启用档案，避免认证查询的 MySQL 旧快照影响确认校验。"""
        for model, id, label in [(CustomerModel, customer_id, "客户"), (WarehouseModel, warehouse_id, "仓库")]:
            row = (await self.db.execute(select(model).where(model.id == id).with_for_update(read=True))).scalar_one_or_none()
            if row is None or row.is_deleted:
                raise CustomException(msg=f"{label}不存在或已删除", status_code=404)
            if row.status != EnableStatus.ENABLED:
                raise CustomException(msg=f"{label}已停用", status_code=400)
        goods = (await self.db.execute(select(GoodsModel).where(GoodsModel.id.in_(goods_ids)).order_by(GoodsModel.id).with_for_update(read=True))).scalars().all()
        if {row.id for row in goods if not row.is_deleted} != goods_ids:
            raise CustomException(msg="部分商品不存在或已删除", status_code=404)
        if any(row.status != EnableStatus.ENABLED for row in goods):
            raise CustomException(msg="部分商品已停用", status_code=400)

    async def returned_totals(self, source_id: int) -> dict[int, ReturnedTotals]:
        """跨数据范围当前读汇总有效退货，调用方必须先锁来源主单。"""
        statement = (
            select(SaleReturnItemModel.source_sale_out_item_id, SaleReturnItemModel.quantity, SaleReturnItemModel.line_amount, SaleReturnItemModel.cost_amount)
            .join(self.model, self.model.id == SaleReturnItemModel.sale_return_id)
            .where(self.model.source_sale_out_id == source_id, self.model.status == DocumentStatus.CONFIRMED, self.model.is_deleted.is_(False), SaleReturnItemModel.is_deleted.is_(False))
            .with_for_update()
        )
        totals: dict[int, ReturnedTotals] = {}
        for item_id, quantity, amount, cost in (await self.db.execute(statement)).all():
            if item_id is not None:
                total = totals.setdefault(item_id, ReturnedTotals())
                total.quantity += quantity
                total.amount += amount
                total.cost += cost
        return totals

    async def create_draft(self, values: dict[str, Any], items: list[SaleReturnItemValues]) -> SaleReturnModel:
        """主从表草稿同步写入，不影响库存及应收。"""
        document = await self.create(values)
        await self._add_items(document.id, items)
        return document

    async def update_draft(self, id: int, version: int, values: dict[str, Any], items: list[SaleReturnItemValues]) -> None:
        """条件更新成功后替换草稿明细，不能替换已入账行。"""
        await self._update_state(id, DocumentStatus.DRAFT, version, values)
        await self.db.execute(delete(SaleReturnItemModel).where(SaleReturnItemModel.sale_return_id == id))
        await self._add_items(id, items)

    async def delete_draft(self, id: int, version: int) -> None:
        """按版本软删除主单及全部明细。"""
        values = self._soft_delete_values()
        await self._update_state(id, DocumentStatus.DRAFT, version, values)
        await self.db.execute(
            update(SaleReturnItemModel)
            .where(
                SaleReturnItemModel.sale_return_id == id,
                SaleReturnItemModel.is_deleted.is_(False),
            )
            .values(**values, updated_id=self.auth.user.id, updated_time=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
        await self.db.flush()

    async def confirm(self, document: SaleReturnModel, now: datetime, total: Decimal, items: list[SaleReturnItemValues]) -> None:
        """占用单据版本并固化本次入账金额，保留草稿行 ID 供流水关联。"""
        await self._update_state(
            document.id,
            DocumentStatus.DRAFT,
            document.version,
            {
                "status": DocumentStatus.CONFIRMED,
                "confirmed_id": self.auth.user.id,
                "confirmed_time": now,
                "return_amount": total,
            },
        )
        old_items = await self.get_items(document.id, lock=True)
        if len(old_items) != len(items):
            raise CustomException(msg="退货明细发生变化，请刷新后重试", status_code=409)
        for original, item in zip(old_items, items, strict=True):
            if original.source_sale_out_item_id != item["source_sale_out_item_id"]:
                raise CustomException(msg="退货来源明细发生变化", status_code=409)
            await self.db.execute(
                update(SaleReturnItemModel)
                .where(SaleReturnItemModel.id == original.id)
                .values(
                    line_amount=item["line_amount"],
                    cost_amount=item["cost_amount"],
                    updated_id=self.auth.user.id,
                    updated_time=now,
                )
                .execution_options(synchronize_session=False)
            )
        await self.db.flush()

    async def void(self, document: SaleReturnModel, now: datetime, reason: str) -> None:
        """版本和状态一致才允许作废，原金额和商品快照不变。"""
        await self._update_state(
            document.id,
            DocumentStatus.CONFIRMED,
            document.version,
            {
                "status": DocumentStatus.VOIDED,
                "voided_id": self.auth.user.id,
                "voided_time": now,
                "void_reason": reason,
            },
        )

    async def _update_state(self, id: int, state: DocumentStatus, version: int, values: dict[str, Any]) -> None:
        """所有修改使用状态、数据权限及版本 CAS，冲突时交由请求事务回滚。"""
        conditions = await self._build_conditions(id=id, status=state, version=version)
        result = await self.db.execute(
            update(self.model)
            .where(*conditions)
            .values(
                **values,
                version=version + 1,
                updated_id=self.auth.user.id,
                updated_time=datetime.now(UTC),
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise CustomException(msg="退货单版本或状态已变化，请刷新后重试", status_code=409)

    async def _add_items(self, id: int, items: list[SaleReturnItemValues]) -> None:
        """保存带审计用户的来源明细快照。"""
        self.db.add_all([SaleReturnItemModel(sale_return_id=id, created_id=self.auth.user.id, updated_id=self.auth.user.id, **row) for row in items])
        await self.db.flush()

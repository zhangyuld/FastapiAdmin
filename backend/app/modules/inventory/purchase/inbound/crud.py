from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, TypedDict

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.inventory.basic.model import SupplierModel, WarehouseModel
from app.modules.inventory.enums import DocumentStatus
from app.modules.system.user.model import UserModel

from ..model import PurchaseInItemModel, PurchaseInModel, PurchaseReturnItemModel, PurchaseReturnModel
from .schema import PurchaseInCreateSchema, PurchaseInUpdateSchema


class PurchaseInItemValues(TypedDict):
    """业务层整理的明细快照，数据库层不再计算金额。"""

    line_no: int
    goods_id: int
    goods_code: str
    goods_name: str
    spec: str | None
    unit: str
    quantity: Decimal
    unit_price: Decimal
    line_amount: Decimal


@dataclass
class PurchaseInNames:
    """批量加载的关联名称，用于主单列表及详情展示。"""

    suppliers: dict[int, str]
    warehouses: dict[int, str]
    users: dict[int, str]


class PurchaseInCRUD(CRUDBase[PurchaseInModel, PurchaseInCreateSchema, PurchaseInUpdateSchema]):
    """采购入库数据层，沿用单据数据权限，仅 flush、不提交事务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """初始化入库主单的数据访问上下文。"""
        super().__init__(model=PurchaseInModel, auth=auth, db=db)

    async def get_document(self, id: int, *, lock: bool = False) -> PurchaseInModel | None:
        """按数据权限读取主单，同时刷新条件更新后的 ORM 缓存。"""
        conditions = await self._build_conditions(id=id)
        options = [selectinload(self.model.created_by), selectinload(self.model.updated_by)] if lock else self._loader_options()
        statement = select(self.model).where(*conditions).options(*options).execution_options(populate_existing=True)
        if lock:
            # 单据加锁不连查用户，避免 MySQL 将审计用户也加入排他锁范围。
            statement = statement.with_for_update(of=self.model)
        return (await self.db.execute(statement)).scalars().first()

    async def transition(self, document: PurchaseInModel, target: DocumentStatus, operated_time: datetime, reason: str | None = None) -> None:
        """按原状态和版本占用单据；请求回滚时状态与记账一并撤销。"""
        conditions = await self._build_conditions(id=document.id, status=document.status, version=document.version)
        values: dict[str, Any] = {
            "status": target,
            "version": document.version + 1,
            "updated_id": self.auth.user.id,
            "updated_time": operated_time,
        }
        if target == DocumentStatus.CONFIRMED:
            values.update(confirmed_id=self.auth.user.id, confirmed_time=operated_time)
        else:
            values.update(voided_id=self.auth.user.id, voided_time=operated_time, void_reason=reason)
        result = await self.db.execute(update(self.model).where(*conditions).values(**values).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise CustomException(msg="单据版本或状态已变化，请刷新后重试", status_code=409)

    async def has_active_returns(self, purchase_in_id: int) -> bool:
        """跨数据范围检查下游退货，不能因当前用户看不到退货而允许冲销。"""
        return (
            await self.db.scalar(
                select(PurchaseReturnModel.id)
                .where(
                    PurchaseReturnModel.source_purchase_in_id == purchase_in_id,
                    PurchaseReturnModel.is_deleted.is_(False),
                    PurchaseReturnModel.status != DocumentStatus.VOIDED,
                )
                .limit(1)
                .with_for_update()
            )
            is not None
        )

    async def validate_return_draft(self, purchase_in_id: int, return_id: int) -> bool:
        """编辑来源时，只接受有数据权限且属于该入库单的退货草稿。"""
        return_crud = CRUDBase(model=PurchaseReturnModel, auth=self.auth, db=self.db)
        conditions = await return_crud._build_conditions(id=return_id)
        document = (await self.db.execute(select(PurchaseReturnModel).where(*conditions).with_for_update())).scalar_one_or_none()
        return document is not None and document.source_purchase_in_id == purchase_in_id and document.status == DocumentStatus.DRAFT

    async def returned_quantities(self, purchase_in_id: int, *, lock: bool = True) -> dict[int, Decimal]:
        """按来源明细汇总全部已确认退货，草稿不占用、作废退货不扣减。"""
        statement = (
            select(PurchaseReturnItemModel.source_purchase_in_item_id, PurchaseReturnItemModel.quantity)
            .join(PurchaseReturnModel, PurchaseReturnModel.id == PurchaseReturnItemModel.purchase_return_id)
            .where(
                PurchaseReturnModel.source_purchase_in_id == purchase_in_id,
                PurchaseReturnModel.status == DocumentStatus.CONFIRMED,
                PurchaseReturnModel.is_deleted.is_(False),
                PurchaseReturnItemModel.is_deleted.is_(False),
            )
        )
        if lock:
            statement = statement.with_for_update()
        # 当前读避免 MySQL REPEATABLE READ 沿用认证查询时的旧快照。
        quantities: dict[int, Decimal] = {}
        for item_id, quantity in (await self.db.execute(statement)).all():
            if item_id is not None:
                quantities[item_id] = quantities.get(item_id, Decimal("0.000")) + quantity
        return quantities

    async def return_totals(self, purchase_in_id: int, *, lock: bool = False) -> tuple[int, Decimal]:
        """汇总所有有效已确认退货的金额，草稿和作废单不计入。"""
        statement = select(PurchaseReturnModel.total_amount).where(
            PurchaseReturnModel.source_purchase_in_id == purchase_in_id,
            PurchaseReturnModel.status == DocumentStatus.CONFIRMED,
            PurchaseReturnModel.is_deleted.is_(False),
        )
        if lock:
            statement = statement.with_for_update()
        amounts = (await self.db.execute(statement)).scalars().all()
        return len(amounts), sum(amounts, Decimal("0.00"))

    async def related_returns(self, purchase_in_id: int, page_no: int, page_size: int) -> PageResultSchema:
        """分页读取当前用户可见的关联退货，包含草稿和作废历史。"""
        return_crud = CRUDBase(model=PurchaseReturnModel, auth=self.auth, db=self.db)
        return await return_crud.page(
            offset=(page_no - 1) * page_size,
            limit=page_size,
            order_by=[{"id": "desc"}],
            search={"source_purchase_in_id": purchase_in_id},
        )

    async def get_items(self, purchase_in_id: int, *, lock: bool = False) -> Sequence[PurchaseInItemModel]:
        """读取已授权主单的有效明细，按行号排序。"""
        statement = (
            select(PurchaseInItemModel)
            .where(
                PurchaseInItemModel.purchase_in_id == purchase_in_id,
                PurchaseInItemModel.is_deleted.is_(False),
            )
            .order_by(PurchaseInItemModel.line_no)
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return (await self.db.execute(statement)).scalars().all()

    async def get_name_maps(self, documents: Sequence[PurchaseInModel]) -> PurchaseInNames:
        """批量补关联名称，历史展示不受档案停用或软删除影响。"""
        supplier_ids = {document.supplier_id for document in documents}
        warehouse_ids = {document.warehouse_id for document in documents}
        user_ids = {id for document in documents for id in (document.confirmed_id, document.voided_id) if id is not None}
        suppliers = dict((await self.db.execute(select(SupplierModel.id, SupplierModel.supplier_name).where(SupplierModel.id.in_(supplier_ids)))).all()) if supplier_ids else {}
        warehouses = dict((await self.db.execute(select(WarehouseModel.id, WarehouseModel.warehouse_name).where(WarehouseModel.id.in_(warehouse_ids)))).all()) if warehouse_ids else {}
        users = dict((await self.db.execute(select(UserModel.id, UserModel.name).where(UserModel.id.in_(user_ids)))).all()) if user_ids else {}
        return PurchaseInNames(suppliers=suppliers, warehouses=warehouses, users=users)

    async def create_draft(self, values: dict[str, Any], items: list[PurchaseInItemValues]) -> PurchaseInModel:
        """保存主单及商品快照，同一次请求事务中任一失败都会回滚。"""
        document = await self.create(values)
        await self._add_items(document.id, items)
        return document

    async def update_draft(self, id: int, version: int, values: dict[str, Any], items: list[PurchaseInItemValues]) -> bool:
        """先原子校验主单状态和版本，成功后完整替换草稿明细。"""
        conditions = await self._build_conditions(id=id, status=DocumentStatus.DRAFT, version=version)
        statement = (
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
        result = await self.db.execute(statement)
        if result.rowcount != 1:
            return False
        # 草稿明细尚未入账，可物理替换；已确认单据不会通过上面的条件更新。
        await self.db.execute(delete(PurchaseInItemModel).where(PurchaseInItemModel.purchase_in_id == id))
        await self._add_items(id, items)
        return True

    async def delete_draft(self, id: int, version: int) -> bool:
        """按版本软删除草稿及其明细，保留审计字段。"""
        conditions = await self._build_conditions(id=id, status=DocumentStatus.DRAFT, version=version)
        values = {
            **self._soft_delete_values(),
            "version": version + 1,
            "updated_id": self.auth.user.id,
            "updated_time": datetime.now(UTC),
        }
        result = await self.db.execute(update(self.model).where(*conditions).values(**values).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            return False
        item_values = {key: value for key, value in values.items() if key != "version"}
        await self.db.execute(
            update(PurchaseInItemModel)
            .where(
                PurchaseInItemModel.purchase_in_id == id,
                PurchaseInItemModel.is_deleted.is_(False),
            )
            .values(**item_values)
            .execution_options(synchronize_session=False)
        )
        await self.db.flush()
        return True

    async def _add_items(self, purchase_in_id: int, items: list[PurchaseInItemValues]) -> None:
        """批量写入带创建人、更新人的商品快照。"""
        self.db.add_all([PurchaseInItemModel(purchase_in_id=purchase_in_id, created_id=self.auth.user.id, updated_id=self.auth.user.id, **item) for item in items])
        await self.db.flush()

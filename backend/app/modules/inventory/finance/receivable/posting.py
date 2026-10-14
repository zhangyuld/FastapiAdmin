from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.modules.inventory.enums import BusinessOperationType, FinanceBillType, SettlementStatus

from ..model import FundAllocationModel, ReceivableModel


class ReceivableService:
    """模块内应收记账服务，原账单保留、冲销另记反向账单。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """沿用业务事务与操作人。"""
        self.auth = auth
        self.db = db

    async def create(self, *, customer_id: int, business_type: str, business_id: int, business_no: str, amount: Decimal, bill_date: date) -> None:
        """生成带方向的销售应收，退货传负金额，零金额直接标为已结清。"""
        self.db.add(
            ReceivableModel(
                customer_id=customer_id,
                business_type=business_type,
                operation_type=BusinessOperationType.CONFIRM,
                business_id=business_id,
                business_no=business_no,
                amount=amount,
                allocated_amount=Decimal("0.00"),
                unallocated_amount=abs(amount),
                bill_date=bill_date,
                status=SettlementStatus.SETTLED if amount == 0 else SettlementStatus.UNSETTLED,
                created_id=self.auth.user.id,
                updated_id=self.auth.user.id,
            )
        )
        await self.db.flush()

    async def lock_reversible(self, business_type: str, business_id: int) -> ReceivableModel:
        """锁定原应收并拒绝核销中的账单，后续核销也必须先锁同一账单。"""
        statement = (
            select(ReceivableModel)
            .where(
                ReceivableModel.business_type == business_type,
                ReceivableModel.business_id == business_id,
                ReceivableModel.operation_type == BusinessOperationType.CONFIRM,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        receivable = (await self.db.execute(statement)).scalar_one_or_none()
        if receivable is None or receivable.is_deleted:
            raise CustomException(msg="原应收账单不存在，不能作废", status_code=409)
        allocation = await self.db.scalar(
            select(FundAllocationModel.id)
            .where(
                FundAllocationModel.bill_type == FinanceBillType.RECEIVABLE,
                FundAllocationModel.bill_id == receivable.id,
                FundAllocationModel.is_deleted.is_(False),
            )
            .limit(1)
            .with_for_update()
        )
        if receivable.allocated_amount != 0 or allocation is not None or receivable.unallocated_amount != abs(receivable.amount):
            raise CustomException(msg="应收账单存在核销，请先撤销核销后再作废", status_code=409)
        return receivable

    async def reverse(self, original: ReceivableModel, reason: str) -> None:
        """按原金额生成反向应收，原账单和核销字段保持不变。"""
        self.db.add(
            ReceivableModel(
                customer_id=original.customer_id,
                business_type=original.business_type,
                operation_type=BusinessOperationType.VOID,
                business_id=original.business_id,
                business_no=original.business_no,
                amount=-original.amount,
                allocated_amount=Decimal("0.00"),
                unallocated_amount=abs(original.amount),
                bill_date=original.bill_date,
                status=SettlementStatus.SETTLED if original.amount == 0 else SettlementStatus.UNSETTLED,
                reversal_id=original.id,
                remark=reason,
                created_id=self.auth.user.id,
                updated_id=self.auth.user.id,
            )
        )
        await self.db.flush()

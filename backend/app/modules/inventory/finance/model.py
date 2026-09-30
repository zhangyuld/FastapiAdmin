from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin, UserMixin


class ReceivableModel(ModelMixin, UserMixin):
    """不可变应收增减账单，正数增加应收、负数冲减应收。"""

    __tablename__ = "ims_receivable"
    __table_args__ = (
        UniqueConstraint("business_type", "business_id", "operation_type", name="uq_ims_receivable_business_operation"),
        CheckConstraint("allocated_amount >= 0", name="ck_ims_receivable_allocated_amount"),
        CheckConstraint("unallocated_amount >= 0", name="ck_ims_receivable_unallocated_amount"),
        Index("ix_ims_receivable_customer_status_date", "customer_id", "status", "bill_date"),
        Index("ix_ims_receivable_business_no", "business_no"),
        {"comment": "应收账单"},
    )

    customer_id: Mapped[int] = mapped_column(ForeignKey("ims_customer.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="客户ID")
    business_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="来源业务类型")
    operation_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="操作类型(confirm/void)")
    business_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="来源业务ID")
    business_no: Mapped[str] = mapped_column(String(64), nullable=False, comment="来源业务单号")
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, comment="带方向应收变动金额")
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False, comment="已核销绝对金额")
    unallocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, comment="未核销绝对金额")
    bill_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="账单日期")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:未结清 1:部分结清 2:已结清)")
    reversal_id: Mapped[int | None] = mapped_column(ForeignKey("ims_receivable.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="被冲销应收记录ID")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")


class PayableModel(ModelMixin, UserMixin):
    """不可变应付增减账单，正数增加应付、负数冲减应付。"""

    __tablename__ = "ims_payable"
    __table_args__ = (
        UniqueConstraint("business_type", "business_id", "operation_type", name="uq_ims_payable_business_operation"),
        CheckConstraint("allocated_amount >= 0", name="ck_ims_payable_allocated_amount"),
        CheckConstraint("unallocated_amount >= 0", name="ck_ims_payable_unallocated_amount"),
        Index("ix_ims_payable_supplier_status_date", "supplier_id", "status", "bill_date"),
        Index("ix_ims_payable_business_no", "business_no"),
        {"comment": "应付账单"},
    )

    supplier_id: Mapped[int] = mapped_column(ForeignKey("ims_supplier.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="供应商ID")
    business_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="来源业务类型")
    operation_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="操作类型(confirm/void)")
    business_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="来源业务ID")
    business_no: Mapped[str] = mapped_column(String(64), nullable=False, comment="来源业务单号")
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, comment="带方向应付变动金额")
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False, comment="已核销绝对金额")
    unallocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, comment="未核销绝对金额")
    bill_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="账单日期")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:未结清 1:部分结清 2:已结清)")
    reversal_id: Mapped[int | None] = mapped_column(ForeignKey("ims_payable.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="被冲销应付记录ID")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")


class FundTransactionModel(ModelMixin, UserMixin):
    """V2 收付款及退款单，记录资金总额和已核销金额。"""

    __tablename__ = "ims_fund_transaction"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_ims_fund_transaction_amount"),
        CheckConstraint("allocated_amount >= 0", name="ck_ims_fund_transaction_allocated_amount"),
        CheckConstraint("allocated_amount <= amount", name="ck_ims_fund_transaction_allocation_limit"),
        Index("ix_ims_fund_transaction_status_date", "status", "business_date"),
        Index("ix_ims_fund_transaction_party", "party_type", "party_id"),
        {"comment": "资金收付款单"},
    )

    transaction_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="资金单号")
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="资金类型(receipt/payment/refund)")
    party_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="往来对象类型(customer/supplier)")
    party_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="客户或供应商ID")
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, comment="资金单总额")
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False, comment="已分配金额")
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False, comment="支付方式")
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="资金发生日期")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:草稿 1:已确认 2:已作废)")
    confirmed_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="确认人ID")
    confirmed_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="确认时间")
    voided_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="作废人ID")
    voided_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="作废时间")
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="作废原因")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="乐观锁版本")


class FundAllocationModel(ModelMixin, UserMixin):
    """V2 资金单与应收应付账单的核销明细。"""

    __tablename__ = "ims_fund_allocation"
    __table_args__ = (
        UniqueConstraint("fund_transaction_id", "bill_type", "bill_id", name="uq_ims_fund_allocation_transaction_bill"),
        CheckConstraint("allocated_amount > 0", name="ck_ims_fund_allocation_amount"),
        Index("ix_ims_fund_allocation_bill", "bill_type", "bill_id"),
        {"comment": "资金核销明细"},
    )

    fund_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("ims_fund_transaction.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="资金单ID",
    )
    bill_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="账单类型(receivable/payable)")
    bill_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="应收或应付账单ID")
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, comment="本次核销金额")

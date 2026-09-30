from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin, UserMixin


class SaleOutModel(ModelMixin, UserMixin):
    """销售出库单主表，确认后扣减库存并生成应收。"""

    __tablename__ = "ims_sale_out"
    __table_args__ = (
        CheckConstraint("original_amount >= 0", name="ck_ims_sale_out_original_amount"),
        CheckConstraint("discount_amount >= 0", name="ck_ims_sale_out_discount_amount"),
        CheckConstraint("receivable_amount >= 0", name="ck_ims_sale_out_receivable_amount"),
        CheckConstraint("discount_amount <= original_amount", name="ck_ims_sale_out_discount_limit"),
        Index("ix_ims_sale_out_status_date", "status", "business_date"),
        Index("ix_ims_sale_out_customer_date", "customer_id", "business_date"),
        Index("ix_ims_sale_out_warehouse_date", "warehouse_id", "business_date"),
        {"comment": "销售出库单"},
    )

    order_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="销售出库单号")
    customer_id: Mapped[int] = mapped_column(ForeignKey("ims_customer.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="客户ID")
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("ims_warehouse.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="出库仓库ID")
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="业务日期")
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False, comment="原价合计")
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False, comment="优惠金额")
    receivable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False, comment="实际应收金额")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:草稿 1:已确认 2:已作废)")
    confirmed_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="确认人ID")
    confirmed_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="确认时间")
    voided_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="作废人ID")
    voided_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="作废时间")
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="作废原因")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="乐观锁版本")


class SaleOutItemModel(ModelMixin, UserMixin):
    """销售出库明细，确认时固化移动平均出库成本。"""

    __tablename__ = "ims_sale_out_item"
    __table_args__ = (
        UniqueConstraint("sale_out_id", "line_no", name="uq_ims_sale_out_item_line"),
        CheckConstraint("line_no > 0", name="ck_ims_sale_out_item_line_no"),
        CheckConstraint("quantity > 0", name="ck_ims_sale_out_item_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_ims_sale_out_item_unit_price"),
        CheckConstraint("line_amount >= 0", name="ck_ims_sale_out_item_line_amount"),
        CheckConstraint("unit_cost IS NULL OR unit_cost >= 0", name="ck_ims_sale_out_item_unit_cost"),
        CheckConstraint("cost_amount IS NULL OR cost_amount >= 0", name="ck_ims_sale_out_item_cost_amount"),
        Index("ix_ims_sale_out_item_goods", "goods_id"),
        {"comment": "销售出库明细"},
    )

    sale_out_id: Mapped[int] = mapped_column(ForeignKey("ims_sale_out.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True, comment="销售出库单ID")
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="行号")
    goods_id: Mapped[int] = mapped_column(ForeignKey("ims_goods.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="商品ID")
    goods_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="商品编码快照")
    goods_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="商品名称快照")
    spec: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="规格型号快照")
    unit: Mapped[str] = mapped_column(String(32), nullable=False, comment="单位快照")
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, comment="销售数量")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, comment="销售单价")
    line_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, comment="销售金额")
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True, comment="确认时固化的单位成本")
    cost_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True, comment="确认时固化的成本金额")


class SaleReturnModel(ModelMixin, UserMixin):
    """销售退货单主表，确认后恢复库存并冲减应收。"""

    __tablename__ = "ims_sale_return"
    __table_args__ = (
        CheckConstraint("return_amount >= 0", name="ck_ims_sale_return_amount"),
        Index("ix_ims_sale_return_status_date", "status", "business_date"),
        Index("ix_ims_sale_return_customer_date", "customer_id", "business_date"),
        Index("ix_ims_sale_return_warehouse_date", "warehouse_id", "business_date"),
        {"comment": "销售退货单"},
    )

    order_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="销售退货单号")
    customer_id: Mapped[int] = mapped_column(ForeignKey("ims_customer.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="客户ID")
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("ims_warehouse.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="退货仓库ID")
    source_sale_out_id: Mapped[int | None] = mapped_column(ForeignKey("ims_sale_out.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="原销售出库单ID")
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="业务日期")
    return_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False, comment="销售退货金额")
    return_reason: Mapped[str] = mapped_column(String(500), nullable=False, comment="退货原因")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:草稿 1:已确认 2:已作废)")
    confirmed_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="确认人ID")
    confirmed_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="确认时间")
    voided_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="作废人ID")
    voided_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="作废时间")
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="作废原因")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="乐观锁版本")


class SaleReturnItemModel(ModelMixin, UserMixin):
    """销售退货明细，使用原销售成本恢复库存。"""

    __tablename__ = "ims_sale_return_item"
    __table_args__ = (
        UniqueConstraint("sale_return_id", "line_no", name="uq_ims_sale_return_item_line"),
        CheckConstraint("line_no > 0", name="ck_ims_sale_return_item_line_no"),
        CheckConstraint("quantity > 0", name="ck_ims_sale_return_item_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_ims_sale_return_item_unit_price"),
        CheckConstraint("line_amount >= 0", name="ck_ims_sale_return_item_line_amount"),
        CheckConstraint("unit_cost >= 0", name="ck_ims_sale_return_item_unit_cost"),
        CheckConstraint("cost_amount >= 0", name="ck_ims_sale_return_item_cost_amount"),
        Index("ix_ims_sale_return_item_goods", "goods_id"),
        Index("ix_ims_sale_return_item_source", "source_sale_out_item_id"),
        {"comment": "销售退货明细"},
    )

    sale_return_id: Mapped[int] = mapped_column(ForeignKey("ims_sale_return.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True, comment="销售退货单ID")
    source_sale_out_item_id: Mapped[int | None] = mapped_column(ForeignKey("ims_sale_out_item.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="原销售出库明细ID")
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="行号")
    goods_id: Mapped[int] = mapped_column(ForeignKey("ims_goods.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="商品ID")
    goods_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="商品编码快照")
    goods_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="商品名称快照")
    spec: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="规格型号快照")
    unit: Mapped[str] = mapped_column(String(32), nullable=False, comment="单位快照")
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, comment="退货数量")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, comment="退货单价")
    line_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, comment="退货金额")
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, comment="恢复库存单位成本")
    cost_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, comment="恢复库存成本金额")

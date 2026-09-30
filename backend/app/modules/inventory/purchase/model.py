from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin, UserMixin


class PurchaseInModel(ModelMixin, UserMixin):
    """采购入库单主表，确认后驱动库存和应付入账。"""

    __tablename__ = "ims_purchase_in"
    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_ims_purchase_in_total_amount"),
        Index("ix_ims_purchase_in_status_date", "status", "business_date"),
        Index("ix_ims_purchase_in_supplier_date", "supplier_id", "business_date"),
        Index("ix_ims_purchase_in_warehouse_date", "warehouse_id", "business_date"),
        {"comment": "采购入库单"},
    )

    order_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="采购入库单号")
    supplier_id: Mapped[int] = mapped_column(ForeignKey("ims_supplier.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="供应商ID")
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("ims_warehouse.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="入库仓库ID")
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="业务日期")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False, comment="采购总额")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:草稿 1:已确认 2:已作废)")
    confirmed_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="确认人ID")
    confirmed_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="确认时间")
    voided_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="作废人ID")
    voided_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="作废时间")
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="作废原因")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="乐观锁版本")


class PurchaseInItemModel(ModelMixin, UserMixin):
    """采购入库明细，保存商品信息和采购价格快照。"""

    __tablename__ = "ims_purchase_in_item"
    __table_args__ = (
        UniqueConstraint("purchase_in_id", "line_no", name="uq_ims_purchase_in_item_line"),
        CheckConstraint("line_no > 0", name="ck_ims_purchase_in_item_line_no"),
        CheckConstraint("quantity > 0", name="ck_ims_purchase_in_item_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_ims_purchase_in_item_unit_price"),
        CheckConstraint("line_amount >= 0", name="ck_ims_purchase_in_item_line_amount"),
        Index("ix_ims_purchase_in_item_goods", "goods_id"),
        {"comment": "采购入库明细"},
    )

    purchase_in_id: Mapped[int] = mapped_column(ForeignKey("ims_purchase_in.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True, comment="采购入库单ID")
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="行号")
    goods_id: Mapped[int] = mapped_column(ForeignKey("ims_goods.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="商品ID")
    goods_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="商品编码快照")
    goods_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="商品名称快照")
    spec: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="规格型号快照")
    unit: Mapped[str] = mapped_column(String(32), nullable=False, comment="单位快照")
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, comment="采购数量")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, comment="采购单价")
    line_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, comment="行金额")


class PurchaseReturnModel(ModelMixin, UserMixin):
    """采购退货单主表，确认后冲减库存和应付。"""

    __tablename__ = "ims_purchase_return"
    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_ims_purchase_return_total_amount"),
        Index("ix_ims_purchase_return_status_date", "status", "business_date"),
        Index("ix_ims_purchase_return_supplier_date", "supplier_id", "business_date"),
        Index("ix_ims_purchase_return_warehouse_date", "warehouse_id", "business_date"),
        {"comment": "采购退货单"},
    )

    order_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="采购退货单号")
    supplier_id: Mapped[int] = mapped_column(ForeignKey("ims_supplier.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="供应商ID")
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("ims_warehouse.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="退货仓库ID")
    source_purchase_in_id: Mapped[int | None] = mapped_column(ForeignKey("ims_purchase_in.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="原采购入库单ID")
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="业务日期")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False, comment="退货总额")
    return_reason: Mapped[str] = mapped_column(String(500), nullable=False, comment="退货原因")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:草稿 1:已确认 2:已作废)")
    confirmed_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="确认人ID")
    confirmed_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="确认时间")
    voided_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="作废人ID")
    voided_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="作废时间")
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="作废原因")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="乐观锁版本")


class PurchaseReturnItemModel(ModelMixin, UserMixin):
    """采购退货明细，保存原采购来源和退货成本。"""

    __tablename__ = "ims_purchase_return_item"
    __table_args__ = (
        UniqueConstraint("purchase_return_id", "line_no", name="uq_ims_purchase_return_item_line"),
        CheckConstraint("line_no > 0", name="ck_ims_purchase_return_item_line_no"),
        CheckConstraint("quantity > 0", name="ck_ims_purchase_return_item_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_ims_purchase_return_item_unit_price"),
        CheckConstraint("line_amount >= 0", name="ck_ims_purchase_return_item_line_amount"),
        CheckConstraint("unit_cost >= 0", name="ck_ims_purchase_return_item_unit_cost"),
        CheckConstraint("cost_amount >= 0", name="ck_ims_purchase_return_item_cost_amount"),
        Index("ix_ims_purchase_return_item_goods", "goods_id"),
        Index("ix_ims_purchase_return_item_source", "source_purchase_in_item_id"),
        {"comment": "采购退货明细"},
    )

    purchase_return_id: Mapped[int] = mapped_column(ForeignKey("ims_purchase_return.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True, comment="采购退货单ID")
    source_purchase_in_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("ims_purchase_in_item.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="原采购入库明细ID"
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="行号")
    goods_id: Mapped[int] = mapped_column(ForeignKey("ims_goods.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="商品ID")
    goods_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="商品编码快照")
    goods_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="商品名称快照")
    spec: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="规格型号快照")
    unit: Mapped[str] = mapped_column(String(32), nullable=False, comment="单位快照")
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, comment="退货数量")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, comment="退货单价")
    line_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, comment="退货金额")
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, comment="退货出库单位成本")
    cost_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, comment="退货成本金额")

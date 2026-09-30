from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin, UserMixin


class StockBalanceModel(ModelMixin, UserMixin):
    """仓库商品库存余额，是并发扣减和移动平均成本的锁定对象。"""

    __tablename__ = "ims_stock_balance"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "goods_id", name="uq_ims_stock_balance_warehouse_goods"),
        CheckConstraint("quantity >= 0", name="ck_ims_stock_balance_quantity"),
        CheckConstraint("avg_cost >= 0", name="ck_ims_stock_balance_avg_cost"),
        CheckConstraint("stock_amount >= 0", name="ck_ims_stock_balance_amount"),
        Index("ix_ims_stock_balance_goods", "goods_id"),
        {"comment": "库存余额表"},
    )

    warehouse_id: Mapped[int] = mapped_column(ForeignKey("ims_warehouse.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="仓库ID")
    goods_id: Mapped[int] = mapped_column(ForeignKey("ims_goods.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="商品ID")
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"), nullable=False, comment="当前库存数量")
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False, comment="移动平均成本")
    stock_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False, comment="当前库存金额")
    last_business_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最近业务入账时间")
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="并发版本号")


class StockLogModel(ModelMixin, UserMixin):
    """不可变库存流水，记录每次生效或冲销前后的数量快照。"""

    __tablename__ = "ims_stock_log"
    __table_args__ = (
        UniqueConstraint("business_type", "business_item_id", "operation_type", name="uq_ims_stock_log_business_operation"),
        CheckConstraint("before_quantity >= 0", name="ck_ims_stock_log_before_quantity"),
        CheckConstraint("after_quantity >= 0", name="ck_ims_stock_log_after_quantity"),
        CheckConstraint("unit_cost >= 0", name="ck_ims_stock_log_unit_cost"),
        Index("ix_ims_stock_log_warehouse_goods_time", "warehouse_id", "goods_id", "posted_time"),
        Index("ix_ims_stock_log_business", "business_type", "business_id"),
        Index("ix_ims_stock_log_business_no", "business_no"),
        {"comment": "库存流水表"},
    )

    warehouse_id: Mapped[int] = mapped_column(ForeignKey("ims_warehouse.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="仓库ID")
    goods_id: Mapped[int] = mapped_column(ForeignKey("ims_goods.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="商品ID")
    business_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="来源业务类型")
    operation_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="操作类型(confirm/void)")
    business_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="来源业务主表ID")
    business_item_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="来源业务明细ID")
    business_no: Mapped[str] = mapped_column(String(64), nullable=False, comment="来源业务单号快照")
    business_date: Mapped[date] = mapped_column(Date, nullable=False, comment="业务日期")
    change_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, comment="带方向库存变动数量")
    before_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, comment="变动前库存数量")
    after_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, comment="变动后库存数量")
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, comment="本次库存单位成本")
    cost_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, comment="带方向库存成本金额")
    reversal_log_id: Mapped[int | None] = mapped_column(ForeignKey("ims_stock_log.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="被冲销库存流水ID")
    posted_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True, comment="实际入账时间")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")


class StockCheckModel(ModelMixin, UserMixin):
    """库存盘点单主表，确认后按差异生成盘盈盘亏流水。"""

    __tablename__ = "ims_stock_check"
    __table_args__ = (
        Index("ix_ims_stock_check_status_date", "status", "business_date"),
        Index("ix_ims_stock_check_warehouse_date", "warehouse_id", "business_date"),
        {"comment": "库存盘点单"},
    )

    check_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="盘点单号")
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("ims_warehouse.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="盘点仓库ID")
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="盘点日期")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:草稿 1:已确认 2:已作废)")
    confirmed_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="确认人ID")
    confirmed_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="确认时间")
    voided_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="作废人ID")
    voided_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="作废时间")
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="作废原因")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="乐观锁版本")


class StockCheckItemModel(ModelMixin, UserMixin):
    """库存盘点明细，保存盘点创建时的账面数量快照。"""

    __tablename__ = "ims_stock_check_item"
    __table_args__ = (
        UniqueConstraint("stock_check_id", "goods_id", name="uq_ims_stock_check_item_goods"),
        CheckConstraint("system_quantity >= 0", name="ck_ims_stock_check_item_system_quantity"),
        CheckConstraint("actual_quantity >= 0", name="ck_ims_stock_check_item_actual_quantity"),
        CheckConstraint("unit_cost >= 0", name="ck_ims_stock_check_item_unit_cost"),
        Index("ix_ims_stock_check_item_goods", "goods_id"),
        {"comment": "库存盘点明细"},
    )

    stock_check_id: Mapped[int] = mapped_column(ForeignKey("ims_stock_check.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True, comment="盘点单ID")
    goods_id: Mapped[int] = mapped_column(ForeignKey("ims_goods.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="商品ID")
    goods_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="商品编码快照")
    goods_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="商品名称快照")
    spec: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="规格型号快照")
    unit: Mapped[str] = mapped_column(String(32), nullable=False, comment="单位快照")
    system_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, comment="账面数量快照")
    actual_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, comment="实盘数量")
    difference_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, comment="盘点差异数量")
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, comment="差异入账单位成本")
    cost_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, comment="带方向差异成本金额")


class StockOpeningModel(ModelMixin, UserMixin):
    """期初库存单主表，确认后以正式业务流水初始化库存。"""

    __tablename__ = "ims_stock_opening"
    __table_args__ = (
        Index("ix_ims_stock_opening_status_date", "status", "business_date"),
        Index("ix_ims_stock_opening_warehouse_date", "warehouse_id", "business_date"),
        {"comment": "期初库存单"},
    )

    opening_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="期初库存单号")
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("ims_warehouse.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="仓库ID")
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="业务日期")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:草稿 1:已确认 2:已作废)")
    confirmed_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="确认人ID")
    confirmed_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="确认时间")
    voided_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True, comment="作废人ID")
    voided_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="作废时间")
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="作废原因")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="乐观锁版本")


class StockOpeningItemModel(ModelMixin, UserMixin):
    """期初库存明细，保存初始化数量、单位成本和商品快照。"""

    __tablename__ = "ims_stock_opening_item"
    __table_args__ = (
        UniqueConstraint("stock_opening_id", "line_no", name="uq_ims_stock_opening_item_line"),
        UniqueConstraint("stock_opening_id", "goods_id", name="uq_ims_stock_opening_item_goods"),
        CheckConstraint("line_no > 0", name="ck_ims_stock_opening_item_line_no"),
        CheckConstraint("quantity > 0", name="ck_ims_stock_opening_item_quantity"),
        CheckConstraint("unit_cost >= 0", name="ck_ims_stock_opening_item_unit_cost"),
        CheckConstraint("cost_amount >= 0", name="ck_ims_stock_opening_item_cost_amount"),
        Index("ix_ims_stock_opening_item_goods", "goods_id"),
        {"comment": "期初库存明细"},
    )

    stock_opening_id: Mapped[int] = mapped_column(ForeignKey("ims_stock_opening.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True, comment="期初库存单ID")
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="行号")
    goods_id: Mapped[int] = mapped_column(ForeignKey("ims_goods.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="商品ID")
    goods_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="商品编码快照")
    goods_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="商品名称快照")
    spec: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="规格型号快照")
    unit: Mapped[str] = mapped_column(String(32), nullable=False, comment="单位快照")
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, comment="期初数量")
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, comment="期初单位成本")
    cost_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, comment="期初库存金额")

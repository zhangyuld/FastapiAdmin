from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin, UserMixin


class GoodsCategoryModel(ModelMixin, UserMixin):
    """商品分类，支持多级父子结构。"""

    __tablename__ = "ims_goods_category"
    __table_args__ = (
        Index("ix_ims_goods_category_parent_name", "parent_id", "name"),
        Index("ix_ims_goods_category_status_sort", "status", "sort"),
        {"comment": "商品分类表"},
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="分类名称")
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("ims_goods_category.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
        index=True,
        comment="父分类ID",
    )
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="显示排序")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:启用 1:停用)")


class GoodsModel(ModelMixin, UserMixin):
    """商品档案，不保存实时库存。"""

    __tablename__ = "ims_goods"
    __table_args__ = (
        CheckConstraint("reference_cost_price >= 0", name="ck_ims_goods_reference_cost_price"),
        CheckConstraint("sale_price >= 0", name="ck_ims_goods_sale_price"),
        CheckConstraint("stock_min >= 0", name="ck_ims_goods_stock_min"),
        CheckConstraint("stock_max >= 0", name="ck_ims_goods_stock_max"),
        Index("ix_ims_goods_category_status", "category_id", "status"),
        Index("ix_ims_goods_name", "goods_name"),
        {"comment": "商品档案表"},
    )

    category_id: Mapped[int] = mapped_column(
        ForeignKey("ims_goods_category.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        comment="商品分类ID",
    )
    goods_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="商品编码")
    goods_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="商品名称")
    spec: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="规格型号")
    unit: Mapped[str] = mapped_column(String(32), nullable=False, comment="基本单位")
    reference_cost_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False, comment="参考进价")
    sale_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False, comment="默认销售价")
    stock_min: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"), nullable=False, comment="最低库存")
    stock_max: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"), nullable=False, comment="最高库存，0表示不限制")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:启用 1:停用)")


class CustomerModel(ModelMixin, UserMixin):
    """客户档案。"""

    __tablename__ = "ims_customer"
    __table_args__ = (Index("ix_ims_customer_name", "customer_name"), {"comment": "客户档案表"})

    customer_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="客户编码")
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="客户名称")
    contact: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="联系人")
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="联系电话")
    address: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="联系地址")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:启用 1:停用)")


class SupplierModel(ModelMixin, UserMixin):
    """供应商档案。"""

    __tablename__ = "ims_supplier"
    __table_args__ = (Index("ix_ims_supplier_name", "supplier_name"), {"comment": "供应商档案表"})

    supplier_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="供应商编码")
    supplier_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="供应商名称")
    contact: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="联系人")
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="联系电话")
    address: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="联系地址")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:启用 1:停用)")


class WarehouseModel(ModelMixin, UserMixin):
    """仓库档案，默认仓库唯一性由服务层事务保证。"""

    __tablename__ = "ims_warehouse"
    __table_args__ = (
        Index("ix_ims_warehouse_default_status", "is_default", "status"),
        {"comment": "仓库档案表"},
    )

    warehouse_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="仓库编码")
    warehouse_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="仓库名称")
    address: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="仓库地址")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否默认仓库")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:启用 1:停用)")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")

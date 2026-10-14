from decimal import Decimal

from sqlalchemy import Numeric, Select, case, cast, func, literal, select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Subquery

from app.modules.inventory.sale.model import SaleOutItemModel, SaleOutModel


def allocated_sale_amounts(document_ids: Select | None = None) -> Subquery:
    """整单累计分摊优惠后再筛商品，顺序与原单退货分摊一致。"""
    item, document = SaleOutItemModel.__table__.c, SaleOutModel.__table__.c
    order = [item.line_no, item.id]
    cumulative = func.sum(item.line_amount).over(partition_by=item.sale_out_id, order_by=order, rows=(None, 0))
    total = func.sum(item.line_amount).over(partition_by=item.sale_out_id)
    statement = (
        select(item.id, item.line_amount, document.discount_amount, cumulative.label("cumulative"), total.label("total"))
        .select_from(SaleOutItemModel.__table__)
        .join(SaleOutModel.__table__, document.id == item.sale_out_id)
        .where(document.status == 1, document.is_deleted.is_(False), item.is_deleted.is_(False))
    )
    if document_ids is not None:
        statement = statement.where(document.id.in_(document_ids))
    base = statement.subquery("sale_allocation_base")

    def target(amount: ColumnElement[Decimal]) -> ColumnElement[Decimal]:
        """以整数分和余数处理 HALF_UP，避免数据库除法的中间舍入尾差。"""
        cents = cast(func.round(amount * 100, 0), Numeric(65, 0))
        total_cents = cast(func.round(base.c.total * 100, 0), Numeric(65, 0))
        discount_cents = cast(func.round(base.c.discount_amount * 100, 0), Numeric(65, 0))
        net_cents = total_cents - discount_cents
        numerator = cents * net_cents
        denominator = func.nullif(total_cents, 0)
        remainder = func.mod(numerator, denominator)
        quotient = func.floor((numerator - remainder).self_group().op("/")(denominator))
        rounded = quotient + case((remainder * 2 >= denominator, 1), else_=0)
        return case((total_cents == 0, Decimal("0.00")), else_=cast(rounded, Numeric(38, 2)) / literal(Decimal("100.00")))

    return select(base.c.id, (target(base.c.cumulative) - target(base.c.cumulative - base.c.line_amount)).label("sale_amount")).subquery("sale_allocated_lines")

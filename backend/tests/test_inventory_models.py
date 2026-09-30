from sqlalchemy import Numeric, UniqueConstraint

from app.core.base_model import MappedBase
from app.utils.import_util import ImportUtil

EXPECTED_INVENTORY_TABLES = {
    "ims_business_log",
    "ims_customer",
    "ims_document_sequence",
    "ims_fund_allocation",
    "ims_fund_transaction",
    "ims_goods",
    "ims_goods_category",
    "ims_payable",
    "ims_purchase_in",
    "ims_purchase_in_item",
    "ims_purchase_return",
    "ims_purchase_return_item",
    "ims_receivable",
    "ims_sale_out",
    "ims_sale_out_item",
    "ims_sale_return",
    "ims_sale_return_item",
    "ims_stock_balance",
    "ims_stock_check",
    "ims_stock_check_item",
    "ims_stock_log",
    "ims_stock_opening",
    "ims_stock_opening_item",
    "ims_supplier",
    "ims_warehouse",
}


def _unique_column_sets(table_name: str) -> set[tuple[str, ...]]:
    """返回指定表的唯一约束字段集合。"""
    table = MappedBase.metadata.tables[table_name]
    return {tuple(column.name for column in constraint.columns) for constraint in table.constraints if isinstance(constraint, UniqueConstraint)}


def test_inventory_table_contract() -> None:
    """固定 V1、V2 进销存表清单，防止模型扫描遗漏。"""
    ImportUtil.find_models(MappedBase)
    actual = {name for name in MappedBase.metadata.tables if name.startswith("ims_")}
    assert actual == EXPECTED_INVENTORY_TABLES


def test_inventory_idempotency_constraints() -> None:
    """库存与往来流水必须通过数据库唯一约束抵御重复入账。"""
    ImportUtil.find_models(MappedBase)
    assert ("warehouse_id", "goods_id") in _unique_column_sets("ims_stock_balance")
    assert ("business_type", "business_item_id", "operation_type") in _unique_column_sets("ims_stock_log")
    assert ("business_type", "business_id", "operation_type") in _unique_column_sets("ims_receivable")
    assert ("business_type", "business_id", "operation_type") in _unique_column_sets("ims_payable")
    assert ("document_type", "sequence_date") in _unique_column_sets("ims_document_sequence")


def test_inventory_precision_and_delete_policy() -> None:
    """固定数量、成本精度及主从表删除策略。"""
    ImportUtil.find_models(MappedBase)
    stock_log = MappedBase.metadata.tables["ims_stock_log"]
    quantity_type = stock_log.c.change_quantity.type
    cost_type = stock_log.c.unit_cost.type
    amount_type = stock_log.c.cost_amount.type

    assert isinstance(quantity_type, Numeric) and (quantity_type.precision, quantity_type.scale) == (18, 3)
    assert isinstance(cost_type, Numeric) and (cost_type.precision, cost_type.scale) == (18, 4)
    assert isinstance(amount_type, Numeric) and (amount_type.precision, amount_type.scale) == (18, 2)

    purchase_item = MappedBase.metadata.tables["ims_purchase_in_item"]
    header_fk = next(iter(purchase_item.c.purchase_in_id.foreign_keys))
    goods_fk = next(iter(purchase_item.c.goods_id.foreign_keys))
    assert header_fk.ondelete == "CASCADE"
    assert goods_fk.ondelete == "RESTRICT"

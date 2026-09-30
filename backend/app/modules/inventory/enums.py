from enum import IntEnum, StrEnum


class EnableStatus(IntEnum):
    """基础档案启停状态。"""

    ENABLED = 0
    DISABLED = 1


class DocumentStatus(IntEnum):
    """业务单据生命周期状态。"""

    DRAFT = 0
    CONFIRMED = 1
    VOIDED = 2


class SettlementStatus(IntEnum):
    """应收应付核销状态。"""

    UNSETTLED = 0
    PARTIALLY_SETTLED = 1
    SETTLED = 2


class StockBusinessType(StrEnum):
    """库存流水来源业务类型。"""

    OPENING_BALANCE = "opening_balance"
    PURCHASE_IN = "purchase_in"
    PURCHASE_RETURN = "purchase_return"
    SALE_OUT = "sale_out"
    SALE_RETURN = "sale_return"
    STOCK_CHECK_GAIN = "stock_check_gain"
    STOCK_CHECK_LOSS = "stock_check_loss"


class BusinessOperationType(StrEnum):
    """业务生效或冲销操作类型。"""

    CONFIRM = "confirm"
    VOID = "void"


class FundTransactionType(StrEnum):
    """资金单据类型。"""

    RECEIPT = "receipt"
    PAYMENT = "payment"
    REFUND = "refund"


class BusinessPartyType(StrEnum):
    """资金往来对象类型。"""

    CUSTOMER = "customer"
    SUPPLIER = "supplier"


class FinanceBillType(StrEnum):
    """资金核销账单类型。"""

    RECEIVABLE = "receivable"
    PAYABLE = "payable"

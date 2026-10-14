"""应付查询与记账，保留采购销售模块原有记账导入契约。"""

from .posting import PayableService

__all__ = ["PayableService"]

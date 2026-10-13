"""期初库存请求及响应契约，与库存模块内公共状态参数保持一致。"""

from ..document_schema import DeleteBody, DocumentExport, DocumentQuery, OpeningCreateSchema, OpeningUpdateSchema, StockDocumentOut, VersionBody, VoidBody

__all__ = ["OpeningCreateSchema", "OpeningUpdateSchema", "StockDocumentOut", "DocumentQuery", "DocumentExport", "VersionBody", "VoidBody", "DeleteBody"]

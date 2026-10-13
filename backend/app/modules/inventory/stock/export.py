from typing import Any

from app.core.exceptions import CustomException
from app.utils.excel_util import ExcelUtil

from .document_schema import ExportOptions


async def export_rows(rows: list[dict[str, Any]], data: ExportOptions, columns: dict[str, str]) -> bytes:
    """库存模块内按字段白名单和用户顺序生成 CSV 或 Excel。"""
    if not set(data.fields).issubset(columns):
        raise CustomException(msg="导出包含不支持的字段", status_code=422)
    mapping = {field: columns[field] for field in data.fields}
    if data.format == "csv":
        return await ExcelUtil.aexport_list2csv(list_data=rows, mapping_dict=mapping)
    return await ExcelUtil.aexport_list2excel(list_data=rows, mapping_dict=mapping, sheet_name=data.sheet_name or "库存")

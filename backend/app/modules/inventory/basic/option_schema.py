"""基础档案选项查询参数，不暴露审计筛选或任意排序。"""

from pydantic import BaseModel, Field, field_validator


class ArchiveOptionQuery(BaseModel):
    """按编码或名称搜索轻量选项，省略状态时包含启用和停用档案。"""

    keyword: str | None = Field(default=None, max_length=200, description="编码或名称关键词")
    status: int | None = Field(default=None, ge=0, le=1, description="状态(0启用、1停用，省略查询全部)")
    page_no: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=50, ge=1, le=100, description="每页条数，上限100")

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value: str | None) -> str | None:
        """忽略纯空白关键词，不将其作为全量模糊查询条件。"""
        return value.strip() or None if value is not None else None

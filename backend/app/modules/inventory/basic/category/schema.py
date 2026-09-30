from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema, UserByQueryParam, UserBySchema


class GoodsCategoryCreateSchema(BaseModel):
    """商品分类创建参数。"""

    name: str = Field(..., min_length=1, max_length=100, description="分类名称")
    parent_id: int | None = Field(default=None, ge=1, description="父分类ID")
    sort: int = Field(default=0, ge=0, le=9999, description="显示排序")
    status: int = Field(default=0, ge=0, le=1, description="状态(0:启用 1:停用)")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """清理分类名称并拒绝纯空白内容。"""
        name = value.strip()
        if not name:
            raise ValueError("分类名称不能为空")
        return name


class GoodsCategoryUpdateSchema(GoodsCategoryCreateSchema):
    """商品分类修改参数。"""


class GoodsCategoryOutSchema(GoodsCategoryCreateSchema, BaseSchema, UserBySchema):
    """商品分类详情响应。"""

    model_config = ConfigDict(from_attributes=True)

    parent_name: str | None = Field(default=None, max_length=100, description="父分类名称")


class GoodsCategoryTreeOutSchema(GoodsCategoryOutSchema):
    """商品分类树节点响应。"""

    children: list["GoodsCategoryTreeOutSchema"] | None = Field(default=None, description="子分类列表")


class GoodsCategoryQueryParam(BaseQueryParam, UserByQueryParam):
    """商品分类查询参数。"""

    name: str | None = Field(default=None, max_length=100, description="分类名称", json_schema_extra={"q": "like"})
    status: int | None = Field(default=None, ge=0, le=1, description="状态(0:启用 1:停用)", json_schema_extra={"q": "eq"})

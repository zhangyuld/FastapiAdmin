"""产品配置只维护保留参数键，发布以原始 JSON 值进行比较更新。"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CustomException
from app.modules.system.params.model import ParamsModel

PRODUCT_CONFIG_KEY = "zhicang_product_config"


class ProductConfigCRUD:
    """不暴露通用参数写入，避免绕过发布版本检查。"""

    def __init__(self, db: AsyncSession) -> None:
        """绑定请求级事务，不自行提交部分配置。"""
        self.db = db

    async def row(self, for_update: bool = False) -> ParamsModel | None:
        """参数历史键没有唯一约束，重复记录必须明确拒绝。"""
        statement = select(ParamsModel).where(ParamsModel.config_key == PRODUCT_CONFIG_KEY)
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        rows = (await self.db.scalars(statement)).all()
        if len(rows) > 1:
            raise CustomException(msg="产品配置键重复，请超管修复", status_code=409)
        return rows[0] if rows else None

    async def initialize(self, defaults: str) -> None:
        """仅补缺失默认配置和旧框架名称，不覆盖已发布内容。"""
        # 保留参数行作为初始化互斥点；SQLite 用写锁，MySQL/PostgreSQL 用事务行锁。
        await self.db.execute(update(ParamsModel).where(ParamsModel.config_key == "sys_name").values(config_value=ParamsModel.config_value, updated_time=ParamsModel.updated_time))
        anchor = await self.db.scalar(select(ParamsModel.id).where(ParamsModel.config_key == "sys_name").with_for_update().limit(1))
        if anchor is None:
            raise CustomException(msg="系统名称参数尚未初始化", status_code=503)
        await self.db.execute(update(ParamsModel).where(ParamsModel.config_key == "sys_name", ParamsModel.config_value.ilike("%fastapiadmin%")).values(config_value="智仓云"))
        if await self.row(for_update=True) is None:
            self.db.add(ParamsModel(config_name="智仓云产品配置", config_key=PRODUCT_CONFIG_KEY, config_value=defaults, config_type=True, status=0, description="仅产品配置发布接口维护，不进入匿名参数缓存"))
            await self.db.flush()

    async def compare_and_swap(self, row: ParamsModel, updated: str) -> None:
        """并发发布只允许一个请求覆盖读取时的原始 JSON。"""
        result = await self.db.execute(update(ParamsModel).where(ParamsModel.id == row.id, ParamsModel.config_value == row.config_value).values(config_value=updated))
        if result.rowcount != 1:
            raise CustomException(msg="配置已更新，请重新加载后发布", status_code=409)

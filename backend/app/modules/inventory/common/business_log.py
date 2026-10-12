from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema

from .model import BusinessLogModel


class BusinessLogService:
    """与库存、应付使用同一事务的业务状态审计。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        """绑定操作人及会话。"""
        self.auth = auth
        self.db = db

    async def record(
        self,
        *,
        business_type: str,
        business_id: int,
        business_no: str,
        action: str,
        before_status: int,
        after_status: int,
        operated_time: datetime,
        content: str | None = None,
    ) -> None:
        """保存确认或作废的状态变更，异常时随业务一起回滚。"""
        self.db.add(
            BusinessLogModel(
                business_type=business_type,
                business_id=business_id,
                business_no=business_no,
                action=action,
                before_status=before_status,
                after_status=after_status,
                operator_id=self.auth.user.id,
                operated_time=operated_time,
                content=content,
                created_id=self.auth.user.id,
                updated_id=self.auth.user.id,
            )
        )
        await self.db.flush()

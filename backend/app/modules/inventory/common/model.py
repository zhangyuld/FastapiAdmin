from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin, UserMixin


class DocumentSequenceModel(ModelMixin, UserMixin):
    """按单据类型和日期维护并发安全的业务编号序列。"""

    __tablename__ = "ims_document_sequence"
    __table_args__ = (
        UniqueConstraint("document_type", "sequence_date", name="uq_ims_document_sequence_type_date"),
        CheckConstraint("current_value >= 0", name="ck_ims_document_sequence_current_value"),
        {"comment": "业务单据编号序列"},
    )

    document_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="单据类型")
    sequence_date: Mapped[date] = mapped_column(Date, nullable=False, comment="编号日期")
    current_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="当前流水号")
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="并发版本号")


class BusinessLogModel(ModelMixin, UserMixin):
    """记录业务单据创建、确认、作废等关键状态变化。"""

    __tablename__ = "ims_business_log"
    __table_args__ = (
        Index("ix_ims_business_log_business_time", "business_type", "business_id", "operated_time"),
        Index("ix_ims_business_log_business_no", "business_no"),
        {"comment": "业务状态变更日志"},
    )

    business_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="业务类型")
    business_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="业务主表ID")
    business_no: Mapped[str] = mapped_column(String(64), nullable=False, comment="业务单号")
    action: Mapped[str] = mapped_column(String(32), nullable=False, comment="业务动作(create/update/confirm/void)")
    before_status: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="操作前状态")
    after_status: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="操作后状态")
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="业务摘要或变更说明")
    operator_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True, comment="操作人ID")
    operated_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True, comment="操作时间")

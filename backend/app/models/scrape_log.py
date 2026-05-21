from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ScrapeLog (Base, TimestampMixin):
    """抓取任务日志 (scrape_logs)."""

    __tablename__ = "scrape_logs"
    __table_args__ = ({"comment": "抓取任务运行日志"},)

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键",
    )
    source: Mapped[str] = mapped_column(
        Enum("sporttery", "titan007", "other", name="scrape_source"),
        nullable=False,
        comment="数据源",
    )
    job_name: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="任务名",
    )
    status: Mapped[str] = mapped_column(
        Enum("running", "success", "failed", "partial", name="scrape_status"),
        nullable=False,
        index=True,
        comment="任务状态",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="开始时间(Asia/Shanghai)",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="结束时间(Asia/Shanghai)",
    )
    records_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="写入/更新记录数",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="错误信息",
    )

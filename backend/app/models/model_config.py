from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.backtest import BacktestSession
    from app.models.score import SportteryMatchScore
    from app.models.user import User


class ModelConfig (Base, TimestampMixin):
    """模型配置表 (model_configs): 6 维权重 / 阈值 / Kelly 档位 / 抓取调度."""

    __tablename__ = "model_configs"
    __table_args__ = ({"comment": "模型配置: 权重/阈值/Kelly 档位/抓取调度"},)

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键",
    )
    name: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="配置名称",
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建者 FK → users.id",
    )

    weights_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, comment="6 维权重 JSON",
    )
    thresholds_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, comment="推荐阈值 JSON (80/84/78 等)",
    )
    kelly_bands_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, comment="Kelly 3 档范围 JSON",
    )
    scrape_schedule_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="自定义抓取调度 JSON (可选)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0", index=True,
        comment="是否当前激活配置",
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_configs.id", ondelete="SET NULL"),
        nullable=True,
        comment="父配置 FK (迭代血缘)",
    )

    creator: Mapped[User | None] = relationship()
    parent: Mapped[ModelConfig | None] = relationship(
        remote_side="ModelConfig.id", foreign_keys=[parent_id]
    )
    scores: Mapped[list[SportteryMatchScore]] = relationship(
        back_populates="config",
        foreign_keys="SportteryMatchScore.model_config_id",
    )
    backtests: Mapped[list[BacktestSession]] = relationship(back_populates="config")

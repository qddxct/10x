from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DECIMAL,
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.match import SportteryMatch
    from app.models.model_config import ModelConfig
    from app.models.user import User


class SportteryMatchScore (Base, TimestampMixin):
    """竞彩比赛 6 维评分表 (sporttery_match_scores).

    每条记录对应 (比赛, 模型配置) 的评分结果；同一比赛在不同模型配置下可以有多条。
    """

    __tablename__ = "sporttery_match_scores"
    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "model_config_id",
            name="uq_sporttery_scores_match_config",
        ),
        {"comment": "竞彩比赛 6 维评分: 欧赔/亚盘/进球数/意向/压缩/球队统计"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键",
    )
    match_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sporttery_matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="比赛 FK → sporttery_matches.id (逻辑ID)",
    )
    model_config_id: Mapped[int] = mapped_column(
        ForeignKey("model_configs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="模型配置 FK → model_configs.id",
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="操作用户 FK → users.id (系统自动评分时为 NULL)",
    )

    euro_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="欧赔维度得分(0-25)",
    )
    asian_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="亚盘维度得分(0-20)",
    )
    goals_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="进球数维度得分(0-20)",
    )
    intent_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="赛事意向维度得分(0-15)",
    )
    compression_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="压缩强度维度得分(0-20)",
    )
    team_stats_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="球队统计维度得分(0-20)",
    )
    total_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, index=True,
        comment="加权后总分",
    )

    bet_type: Mapped[str | None] = mapped_column(
        Enum("draw", "handicap_draw", name="bet_type"),
        nullable=True,
        comment="推荐投注类型: draw=买平, handicap_draw=让球平",
    )
    kelly_pct: Mapped[Decimal | None] = mapped_column(
        DECIMAL(5, 4), nullable=True, comment="Kelly 建议投注比例(本金占比)",
    )
    is_recommended: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True,
        comment="是否达到推荐阈值",
    )

    actual_hit: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, comment="实际是否命中(结算后回写)",
    )
    bet_amount: Mapped[Decimal | None] = mapped_column(
        DECIMAL(12, 2), nullable=True, comment="实际投注金额(CNY)",
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="操作备注",
    )

    match: Mapped[SportteryMatch] = relationship(back_populates="scores")
    config: Mapped[ModelConfig] = relationship(
        back_populates="scores", foreign_keys=[model_config_id]
    )
    user: Mapped[User | None] = relationship(back_populates="scores")

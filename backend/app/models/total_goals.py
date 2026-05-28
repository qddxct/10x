from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from datetime import date

from sqlalchemy import BigInteger, Boolean, DECIMAL, Date, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.match import SportteryMatch


class TotalGoalRecommendation(Base, TimestampMixin):
    """总进球数推荐结果，每场比赛每个模型版本保留一条最优预测。"""

    __tablename__ = "total_goal_recommendations"
    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "model_version",
            name="uq_total_goal_recommendations_match_version",
        ),
        {"comment": "竞彩总进球数推荐: 精确总进球数 0/1/2/3/4/5/6/7+"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sporttery_matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, default="tg-v1")
    target_goals: Mapped[int] = mapped_column(Integer, nullable=False, comment="0-6 精确球数，7 表示 7+")
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    confidence_pct: Mapped[Decimal | None] = mapped_column(DECIMAL(5, 2), nullable=True)
    bet_odds: Mapped[Decimal | None] = mapped_column(DECIMAL(6, 3), nullable=True)
    is_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    explanation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    match: Mapped[SportteryMatch] = relationship()


class TotalGoalComboRecommendation(Base, TimestampMixin):
    """总进球数 2串1 推荐快照."""

    __tablename__ = "total_goal_combo_recommendations"
    __table_args__ = (
        UniqueConstraint(
            "recommendation_date",
            "rank",
            "model_version",
            name="uq_total_goal_combo_recommendations_date_rank_version",
        ),
        {"comment": "总进球数 2串1 推荐快照"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recommendation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(32), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, default="tg-v1")
    combo_odds: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 3), nullable=True)
    combo_odds_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    avg_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    legs_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False)

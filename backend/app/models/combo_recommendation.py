from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DECIMAL, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ComboRecommendation(Base, TimestampMixin):
    """2串1推荐快照."""

    __tablename__ = "combo_recommendations"
    __table_args__ = (
        UniqueConstraint(
            "recommendation_date",
            "model_config_id",
            "rank",
            name="uq_combo_recommendations_date_model_rank",
        ),
        {"comment": "2串1推荐快照"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recommendation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    model_config_id: Mapped[int] = mapped_column(
        ForeignKey("model_configs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(32), nullable=False)
    combo_odds: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 3), nullable=True)
    avg_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    legs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)

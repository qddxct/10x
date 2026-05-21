from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import DECIMAL, JSON, Date, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.model_config import ModelConfig
    from app.models.user import User


class BacktestSession (Base, TimestampMixin):
    """回测会话 (backtest_sessions)."""

    __tablename__ = "backtest_sessions"
    __table_args__ = ({"comment": "回测会话结果快照"},)

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键",
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="发起用户 FK → users.id",
    )
    model_config_id: Mapped[int] = mapped_column(
        ForeignKey("model_configs.id", ondelete="RESTRICT"),
        nullable=False, index=True,
        comment="模型配置 FK",
    )

    date_from: Mapped[date] = mapped_column(
        Date, nullable=False, comment="回测起始日期",
    )
    date_to: Mapped[date] = mapped_column(
        Date, nullable=False, comment="回测结束日期",
    )

    total_bets: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="总投注笔数",
    )
    hit_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="命中笔数",
    )
    hit_rate: Mapped[Decimal] = mapped_column(
        DECIMAL(6, 4), nullable=False, default=Decimal("0"), comment="命中率",
    )
    roi: Mapped[Decimal] = mapped_column(
        DECIMAL(8, 4), nullable=False, default=Decimal("0"), comment="定额 ROI",
    )
    profit_loss: Mapped[Decimal] = mapped_column(
        DECIMAL(14, 2), nullable=False, default=Decimal("0"),
        comment="定额盈亏金额(CNY)",
    )

    results_by_score: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="分分档结果 JSON",
    )
    results_by_league: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="分联赛结果 JSON",
    )
    equity_curve: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True, comment="资金曲线 JSON",
    )

    mode: Mapped[str] = mapped_column(
        Enum("fixed", "kelly", "both", name="backtest_mode"),
        nullable=False, default="both",
        comment="仓位模式: fixed 定额/kelly 凯利/both 两者",
    )
    initial_capital: Mapped[Decimal | None] = mapped_column(
        DECIMAL(14, 2), nullable=True, comment="初始本金(CNY)",
    )
    kelly_profit_loss: Mapped[Decimal] = mapped_column(
        DECIMAL(14, 2), nullable=False, default=Decimal("0"),
        comment="Kelly 盈亏金额(CNY)",
    )
    kelly_roi: Mapped[Decimal] = mapped_column(
        DECIMAL(8, 4), nullable=False, default=Decimal("0"), comment="Kelly ROI",
    )
    fixed_stake: Mapped[Decimal | None] = mapped_column(
        DECIMAL(14, 2), nullable=True, comment="每场固定投注金额(CNY)",
    )
    bets_detail: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True, comment="每场下注明细 JSON 快照",
    )

    user: Mapped[User | None] = relationship(back_populates="backtests")
    config: Mapped[ModelConfig] = relationship(
        back_populates="backtests", foreign_keys=[model_config_id]
    )

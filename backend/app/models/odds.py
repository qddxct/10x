from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DECIMAL, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.match import SportteryMatch


class SportteryMatchOdds (Base, TimestampMixin):
    """竞彩比赛赔率快照表 (sporttery_match_odds).

    每条记录是 (比赛, 来源) 的最新快照：欧赔(HAD) 与 亚盘(HHAD) 同表存储。
    """

    __tablename__ = "sporttery_match_odds"
    __table_args__ = (
        Index("ix_sporttery_odds_match_source", "match_id", "source"),
        {"comment": "竞彩比赛赔率快照: 欧赔+亚盘, 按 source 区分"},
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
    source: Mapped[str] = mapped_column(
        Enum("sporttery", "titan007", "other", name="odds_source"),
        nullable=False,
        comment="赔率来源: sporttery=竞彩官方, titan007=球探网聚合",
    )

    win_odds: Mapped[Decimal | None] = mapped_column(
        DECIMAL(6, 3), nullable=True, comment="欧赔主胜(HAD H)",
    )
    draw_odds: Mapped[Decimal | None] = mapped_column(
        DECIMAL(6, 3), nullable=True, comment="欧赔平局(HAD D)",
    )
    lose_odds: Mapped[Decimal | None] = mapped_column(
        DECIMAL(6, 3), nullable=True, comment="欧赔客胜(HAD A)",
    )

    handicap_value: Mapped[Decimal | None] = mapped_column(
        DECIMAL(4, 2), nullable=True,
        comment="让球值(家球视角,负=让给客队); 如 -1.00, 0.25",
    )
    win_handicap_odds: Mapped[Decimal | None] = mapped_column(
        DECIMAL(6, 3), nullable=True, comment="让球主胜(HHAD H)",
    )
    draw_handicap_odds: Mapped[Decimal | None] = mapped_column(
        DECIMAL(6, 3), nullable=True, comment="让球平(HHAD D)",
    )
    lose_handicap_odds: Mapped[Decimal | None] = mapped_column(
        DECIMAL(6, 3), nullable=True, comment="让球客胜(HHAD A)",
    )

    asian_handicap: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="亚盘文本描述或让球值字符串(兼容字段)",
    )
    total_goals: Mapped[Decimal | None] = mapped_column(
        DECIMAL(4, 2), nullable=True, comment="大小球盘口(若有)",
    )

    scraped_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="抓取时间(UTC)",
    )

    match: Mapped[SportteryMatch] = relationship(back_populates="odds")

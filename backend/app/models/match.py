from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DECIMAL, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.league import League
    from app.models.odds import SportteryMatchOdds
    from app.models.result import SportteryMatchResult
    from app.models.score import SportteryMatchScore
    from app.models.team_stats import SportteryMatchTeamStats


class SportteryMatch (Base, TimestampMixin):
    """竞彩比赛主表 (sporttery_matches).

    PRIMARY KEY ``id`` 是业务自定义的 12 位逻辑 id，组成：
    ``YYYYMMDD`` + 星期数字(0=周日..6=周六) + 编号3位。

    示例：2026-04-19 周日001 → 202604190001。竞彩官网与球探网 (titan007)
    对同一场比赛使用同一个业务日 + 周X + 编号，因此本 id 跨源唯一。
    """

    __tablename__ = "sporttery_matches"
    __table_args__ = (
        Index("ix_sporttery_matches_date_league", "match_date", "league_id"),
        {"comment": "竞彩比赛主表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=False,
        comment="逻辑ID: YYYYMMDD + 星期(0=周日..6=周六) + 编号3位",
    )
    sporttery_match_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        unique=True,
        index=True,
        comment="竞彩官网 webapi.sporttery.cn 内部 matchId; 仅体彩有元数据时有值",
    )
    match_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True, comment="开赛时间(北京时间)",
    )
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="联赛 FK → leagues.id",
    )
    home_team: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="主队中文名(简体)",
    )
    away_team: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="客队中文名(简体)",
    )
    round: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="竞彩编号(如 周日001)",
    )
    competition_type: Mapped[str] = mapped_column(
        Enum(
            "league",
            "cup",
            "knockout_first_leg",
            "knockout_second_leg",
            name="competition_type",
        ),
        nullable=False,
        default="league",
        comment="赛事类型: 联赛/杯赛/淘汰赛首回合/次回合",
    )
    status: Mapped[str] = mapped_column(
        Enum("scheduled", "in_progress", "finished", name="match_status"),
        nullable=False,
        default="scheduled",
        index=True,
        comment="比赛状态: 未开赛/进行中/已结束",
    )

    # -- 竞彩官网赔率(用于计算奖金，非真实欧赔) --
    had_h: Mapped[Decimal | None] = mapped_column(
        DECIMAL(6, 3), nullable=True, comment="竞彩胜赔率(HAD 主胜)",
    )
    had_d: Mapped[Decimal | None] = mapped_column(
        DECIMAL(6, 3), nullable=True, comment="竞彩平赔率(HAD 平局)",
    )
    had_a: Mapped[Decimal | None] = mapped_column(
        DECIMAL(6, 3), nullable=True, comment="竞彩负赔率(HAD 客胜)",
    )
    hhad_h: Mapped[Decimal | None] = mapped_column(
        DECIMAL(6, 3), nullable=True, comment="竞彩让球胜赔率(HHAD 主胜)",
    )
    hhad_d: Mapped[Decimal | None] = mapped_column(
        DECIMAL(6, 3), nullable=True, comment="竞彩让球平赔率(HHAD 平局)",
    )
    hhad_a: Mapped[Decimal | None] = mapped_column(
        DECIMAL(6, 3), nullable=True, comment="竞彩让球负赔率(HHAD 客胜)",
    )
    hhad_goal_line: Mapped[Decimal | None] = mapped_column(
        DECIMAL(4, 1), nullable=True, comment="竞彩让球数(如 -1, +1, -0.5)",
    )

    league: Mapped[League] = relationship(back_populates="matches")
    odds: Mapped[list[SportteryMatchOdds]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )
    result: Mapped[SportteryMatchResult | None] = relationship(
        back_populates="match", cascade="all, delete-orphan", uselist=False
    )
    team_stats: Mapped[SportteryMatchTeamStats | None] = relationship(
        back_populates="match", cascade="all, delete-orphan", uselist=False
    )
    scores: Mapped[list[SportteryMatchScore]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )

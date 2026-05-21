from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, ForeignKey, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.match import SportteryMatch


class SportteryMatchResult (Base, TimestampMixin):
    """竞彩比赛结果 (sporttery_match_results).

    每场比赛唯一一条记录，记录全场比分、胜平负结果、以及让球胜平负结果。
    """

    __tablename__ = "sporttery_match_results"
    __table_args__ = ({"comment": "竞彩比赛结果: 全场比分 + 胜平负 + 让球胜平负"},)

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键",
    )
    match_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sporttery_matches.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="比赛 FK → sporttery_matches.id (逻辑ID)",
    )

    home_score: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="主队全场进球数",
    )
    away_score: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="客队全场进球数",
    )
    result: Mapped[str] = mapped_column(
        Enum("home_win", "draw", "away_win", name="match_result_enum"),
        nullable=False,
        comment="胜平负结果(主胜/平/客胜)",
    )
    handicap_result: Mapped[str | None] = mapped_column(
        Enum("home_win", "draw", "away_win", name="handicap_result_enum"),
        nullable=True,
        comment="让球胜平负结果(按 match_odds.handicap_value 计算)",
    )

    match: Mapped[SportteryMatch] = relationship(back_populates="result")

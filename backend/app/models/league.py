from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.match import SportteryMatch


class League (Base, TimestampMixin):
    """联赛表 (leagues)."""

    __tablename__ = "leagues"
    __table_args__ = (
        UniqueConstraint("name", "country", name="uq_league_name_country"),
        {"comment": "联赛/赛事字典表"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键",
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, comment="联赛名称(中文)",
    )
    country: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="国家/地区",
    )
    draw_rate_tier: Mapped[str | None] = mapped_column(
        Enum("high", "medium", "low", name="draw_rate_tier"),
        nullable=True,
        comment="历史平局率等级: 高/中/低",
    )

    matches: Mapped[list[SportteryMatch]] = relationship(back_populates="league")

    def __repr__(self) -> str:
        return f"<League id={self.id} name={self.name}>"

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.match import SportteryMatch


class SportteryMatchTeamStats (Base, TimestampMixin):
    """竞彩比赛的球队战绩快照 (sporttery_match_team_stats).

    抓取 sporttery getMatchTablesV2 + getMatchFeatureV1 等 API 聚合而成；
    每场比赛唯一一条记录，赛前快照。
    """

    __tablename__ = "sporttery_match_team_stats"
    __table_args__ = ({"comment": "球队战绩快照: 排名/赛季战绩/主客场/近况/交锋"},)

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

    home_rank: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队联赛排名",
    )
    home_season_wins: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队赛季胜场",
    )
    home_season_draws: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队赛季平场",
    )
    home_season_losses: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队赛季负场",
    )
    home_home_wins: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队主场胜",
    )
    home_home_draws: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队主场平",
    )
    home_home_losses: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队主场负",
    )
    home_recent_form: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="主队近 5-10 场战绩串(W/D/L)",
    )

    away_rank: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队联赛排名",
    )
    away_season_wins: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队赛季胜场",
    )
    away_season_draws: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队赛季平场",
    )
    away_season_losses: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队赛季负场",
    )
    away_away_wins: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队客场胜",
    )
    away_away_draws: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队客场平",
    )
    away_away_losses: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队客场负",
    )
    away_recent_form: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="客队近 5-10 场战绩串(W/D/L)",
    )

    h2h_home_wins: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="交锋:主队胜场",
    )
    h2h_draws: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="交锋:平场",
    )
    h2h_away_wins: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="交锋:客队胜场",
    )

    home_recent_matches_count: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队近期可解析比分场次",
    )
    home_recent_goals_for: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队近期进球",
    )
    home_recent_goals_against: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队近期失球",
    )
    home_recent_goal_diff: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队近期净胜球",
    )
    home_recent_win_by_1: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队近期赢1球场次",
    )
    home_recent_win_by_2plus: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队近期赢2球及以上场次",
    )
    home_recent_loss_by_1: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队近期输1球场次",
    )
    home_recent_loss_by_2plus: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队近期输2球及以上场次",
    )
    home_recent_draw_score_count: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队近期比分打平场次",
    )
    home_recent_low_scoring_count: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队近期总进球<=2场次",
    )
    home_recent_high_scoring_count: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队近期总进球>=4场次",
    )

    away_recent_matches_count: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队近期可解析比分场次",
    )
    away_recent_goals_for: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队近期进球",
    )
    away_recent_goals_against: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队近期失球",
    )
    away_recent_goal_diff: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队近期净胜球",
    )
    away_recent_win_by_1: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队近期赢1球场次",
    )
    away_recent_win_by_2plus: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队近期赢2球及以上场次",
    )
    away_recent_loss_by_1: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队近期输1球场次",
    )
    away_recent_loss_by_2plus: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队近期输2球及以上场次",
    )
    away_recent_draw_score_count: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队近期比分打平场次",
    )
    away_recent_low_scoring_count: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队近期总进球<=2场次",
    )
    away_recent_high_scoring_count: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队近期总进球>=4场次",
    )

    home_home_recent_matches_count: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队主场近期可解析比分场次",
    )
    home_home_recent_goals_for: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队主场近期进球",
    )
    home_home_recent_goals_against: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队主场近期失球",
    )
    home_home_recent_goal_diff: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队主场近期净胜球",
    )
    home_home_recent_win_by_1: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队主场近期赢1球场次",
    )
    home_home_recent_win_by_2plus: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队主场近期赢2球及以上场次",
    )
    home_home_recent_loss_by_1: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队主场近期输1球场次",
    )
    home_home_recent_loss_by_2plus: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="主队主场近期输2球及以上场次",
    )

    away_away_recent_matches_count: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队客场近期可解析比分场次",
    )
    away_away_recent_goals_for: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队客场近期进球",
    )
    away_away_recent_goals_against: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队客场近期失球",
    )
    away_away_recent_goal_diff: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队客场近期净胜球",
    )
    away_away_recent_win_by_1: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队客场近期赢1球场次",
    )
    away_away_recent_win_by_2plus: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队客场近期赢2球及以上场次",
    )
    away_away_recent_loss_by_1: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队客场近期输1球场次",
    )
    away_away_recent_loss_by_2plus: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="客队客场近期输2球及以上场次",
    )

    h2h_matches_count: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="交锋可解析比分场次",
    )
    h2h_home_goals_for: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="交锋中当前主队进球",
    )
    h2h_home_goals_against: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="交锋中当前主队失球",
    )
    h2h_goal_diff: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="交锋中当前主队净胜球",
    )
    h2h_draw_score_count: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="交锋比分打平场次",
    )
    h2h_one_goal_margin_count: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="交锋一球差场次",
    )
    h2h_low_scoring_count: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="交锋总进球<=2场次",
    )
    h2h_high_scoring_count: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="交锋总进球>=4场次",
    )

    scraped_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="抓取时间(UTC)",
    )

    match: Mapped[SportteryMatch] = relationship(back_populates="team_stats")

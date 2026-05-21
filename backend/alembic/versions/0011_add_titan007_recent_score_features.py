"""add Titan007 recent score feature columns

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-26 12:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "sporttery_match_team_stats"
COLUMNS = (
    ("home_recent_matches_count", "主队近期可解析比分场次"),
    ("home_recent_goals_for", "主队近期进球"),
    ("home_recent_goals_against", "主队近期失球"),
    ("home_recent_goal_diff", "主队近期净胜球"),
    ("home_recent_win_by_1", "主队近期赢1球场次"),
    ("home_recent_win_by_2plus", "主队近期赢2球及以上场次"),
    ("home_recent_loss_by_1", "主队近期输1球场次"),
    ("home_recent_loss_by_2plus", "主队近期输2球及以上场次"),
    ("home_recent_draw_score_count", "主队近期比分打平场次"),
    ("home_recent_low_scoring_count", "主队近期总进球<=2场次"),
    ("home_recent_high_scoring_count", "主队近期总进球>=4场次"),
    ("away_recent_matches_count", "客队近期可解析比分场次"),
    ("away_recent_goals_for", "客队近期进球"),
    ("away_recent_goals_against", "客队近期失球"),
    ("away_recent_goal_diff", "客队近期净胜球"),
    ("away_recent_win_by_1", "客队近期赢1球场次"),
    ("away_recent_win_by_2plus", "客队近期赢2球及以上场次"),
    ("away_recent_loss_by_1", "客队近期输1球场次"),
    ("away_recent_loss_by_2plus", "客队近期输2球及以上场次"),
    ("away_recent_draw_score_count", "客队近期比分打平场次"),
    ("away_recent_low_scoring_count", "客队近期总进球<=2场次"),
    ("away_recent_high_scoring_count", "客队近期总进球>=4场次"),
    ("home_home_recent_matches_count", "主队主场近期可解析比分场次"),
    ("home_home_recent_goals_for", "主队主场近期进球"),
    ("home_home_recent_goals_against", "主队主场近期失球"),
    ("home_home_recent_goal_diff", "主队主场近期净胜球"),
    ("home_home_recent_win_by_1", "主队主场近期赢1球场次"),
    ("home_home_recent_win_by_2plus", "主队主场近期赢2球及以上场次"),
    ("home_home_recent_loss_by_1", "主队主场近期输1球场次"),
    ("home_home_recent_loss_by_2plus", "主队主场近期输2球及以上场次"),
    ("away_away_recent_matches_count", "客队客场近期可解析比分场次"),
    ("away_away_recent_goals_for", "客队客场近期进球"),
    ("away_away_recent_goals_against", "客队客场近期失球"),
    ("away_away_recent_goal_diff", "客队客场近期净胜球"),
    ("away_away_recent_win_by_1", "客队客场近期赢1球场次"),
    ("away_away_recent_win_by_2plus", "客队客场近期赢2球及以上场次"),
    ("away_away_recent_loss_by_1", "客队客场近期输1球场次"),
    ("away_away_recent_loss_by_2plus", "客队客场近期输2球及以上场次"),
    ("h2h_matches_count", "交锋可解析比分场次"),
    ("h2h_home_goals_for", "交锋中当前主队进球"),
    ("h2h_home_goals_against", "交锋中当前主队失球"),
    ("h2h_goal_diff", "交锋中当前主队净胜球"),
    ("h2h_draw_score_count", "交锋比分打平场次"),
    ("h2h_one_goal_margin_count", "交锋一球差场次"),
    ("h2h_low_scoring_count", "交锋总进球<=2场次"),
    ("h2h_high_scoring_count", "交锋总进球>=4场次"),
)


def upgrade() -> None:
    for name, comment in COLUMNS:
        op.add_column(
            TABLE,
            sa.Column(name, sa.SmallInteger(), nullable=True, comment=comment),
        )


def downgrade() -> None:
    for name, _comment in reversed(COLUMNS):
        op.drop_column(TABLE, name)

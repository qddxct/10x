"""add 竞彩官网赔率列 to sporttery_matches

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-22 22:00:00.000000

Add 7 columns for Sporttery official odds (HAD / HHAD / goal line) directly
on the ``sporttery_matches`` table.  These are the lottery-prize odds shown
on the 竞彩官网, **not** the real European odds stored in
``sporttery_match_odds`` (which are used for model scoring).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = (
    ("had_h",          sa.DECIMAL(precision=6, scale=3), "竞彩胜赔率(HAD 主胜)"),
    ("had_d",          sa.DECIMAL(precision=6, scale=3), "竞彩平赔率(HAD 平局)"),
    ("had_a",          sa.DECIMAL(precision=6, scale=3), "竞彩负赔率(HAD 客胜)"),
    ("hhad_h",         sa.DECIMAL(precision=6, scale=3), "竞彩让球胜赔率(HHAD 主胜)"),
    ("hhad_d",         sa.DECIMAL(precision=6, scale=3), "竞彩让球平赔率(HHAD 平局)"),
    ("hhad_a",         sa.DECIMAL(precision=6, scale=3), "竞彩让球负赔率(HHAD 客胜)"),
    ("hhad_goal_line", sa.DECIMAL(precision=4, scale=1), "竞彩让球数(如 -1, +1, -0.5)"),
)

TABLE = "sporttery_matches"


def upgrade() -> None:
    for name, col_type, comment in COLUMNS:
        op.add_column(TABLE, sa.Column(name, col_type, nullable=True, comment=comment))


def downgrade() -> None:
    for name, _col_type, _comment in reversed(COLUMNS):
        op.drop_column(TABLE, name)

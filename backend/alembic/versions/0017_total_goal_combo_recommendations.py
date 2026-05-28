"""add total goal combo recommendations

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-28 10:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "total_goal_combo_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("recommendation_date", sa.Date(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False, server_default="tg-v1"),
        sa.Column("combo_odds", sa.DECIMAL(10, 3), nullable=True),
        sa.Column("combo_odds_label", sa.String(length=64), nullable=True),
        sa.Column("avg_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("legs_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint(
            "recommendation_date",
            "rank",
            "model_version",
            name="uq_total_goal_combo_recommendations_date_rank_version",
        ),
    )
    op.create_index(
        "ix_total_goal_combo_recommendations_recommendation_date",
        "total_goal_combo_recommendations",
        ["recommendation_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_total_goal_combo_recommendations_recommendation_date",
        table_name="total_goal_combo_recommendations",
    )
    op.drop_table("total_goal_combo_recommendations")

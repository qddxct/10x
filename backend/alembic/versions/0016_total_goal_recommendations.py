"""add total goal recommendations

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-22 15:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for n in range(8):
        op.add_column(
            "sporttery_matches",
            sa.Column(f"ttg_{n}", sa.DECIMAL(6, 3), nullable=True),
        )

    op.create_table(
        "total_goal_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False, server_default="tg-v1"),
        sa.Column("target_goals", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence_pct", sa.DECIMAL(5, 2), nullable=True),
        sa.Column("bet_odds", sa.DECIMAL(6, 3), nullable=True),
        sa.Column("is_recommended", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("explanation_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["sporttery_matches.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "match_id",
            "model_version",
            name="uq_total_goal_recommendations_match_version",
        ),
    )
    op.create_index(
        "ix_total_goal_recommendations_match_id",
        "total_goal_recommendations",
        ["match_id"],
    )
    op.create_index(
        "ix_total_goal_recommendations_total_score",
        "total_goal_recommendations",
        ["total_score"],
    )
    op.create_index(
        "ix_total_goal_recommendations_is_recommended",
        "total_goal_recommendations",
        ["is_recommended"],
    )


def downgrade() -> None:
    op.drop_index("ix_total_goal_recommendations_is_recommended", table_name="total_goal_recommendations")
    op.drop_index("ix_total_goal_recommendations_total_score", table_name="total_goal_recommendations")
    op.drop_index("ix_total_goal_recommendations_match_id", table_name="total_goal_recommendations")
    op.drop_table("total_goal_recommendations")
    for n in reversed(range(8)):
        op.drop_column("sporttery_matches", f"ttg_{n}")

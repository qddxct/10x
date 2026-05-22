"""add combo recommendations

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-22 11:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "combo_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("recommendation_date", sa.Date(), nullable=False),
        sa.Column("model_config_id", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=32), nullable=False),
        sa.Column("combo_odds", sa.DECIMAL(10, 3), nullable=True),
        sa.Column("avg_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("legs_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["model_config_id"], ["model_configs.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "recommendation_date",
            "model_config_id",
            "rank",
            name="uq_combo_recommendations_date_model_rank",
        ),
    )
    op.create_index(
        "ix_combo_recommendations_recommendation_date",
        "combo_recommendations",
        ["recommendation_date"],
    )
    op.create_index(
        "ix_combo_recommendations_model_config_id",
        "combo_recommendations",
        ["model_config_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_combo_recommendations_model_config_id", table_name="combo_recommendations")
    op.drop_index("ix_combo_recommendations_recommendation_date", table_name="combo_recommendations")
    op.drop_table("combo_recommendations")

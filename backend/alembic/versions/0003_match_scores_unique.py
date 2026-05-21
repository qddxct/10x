"""add unique constraint on match_scores (match_id, model_config_id)

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-21 18:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_scores_match_config", table_name="match_scores")
    op.create_unique_constraint(
        "uq_match_scores_match_config",
        "match_scores",
        ["match_id", "model_config_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_match_scores_match_config", "match_scores", type_="unique")
    op.create_index(
        "ix_scores_match_config",
        "match_scores",
        ["match_id", "model_config_id"],
    )

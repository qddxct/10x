"""add random ticket research artifact type

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-26 17:45:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADED_VALUES = (
    "factor_bucket",
    "combo_simulation",
    "random_baseline",
    "combo_ticket",
    "random_ticket",
    "window_summary",
    "markdown_report",
)
DOWNGRADED_VALUES = (
    "factor_bucket",
    "combo_simulation",
    "random_baseline",
    "combo_ticket",
    "window_summary",
    "markdown_report",
)


def _enum_sql(values: tuple[str, ...]) -> str:
    quoted = ",".join(f"'{value}'" for value in values)
    return f"ENUM({quoted})"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.execute(
            "ALTER TABLE model_research_artifacts "
            f"MODIFY artifact_type {_enum_sql(UPGRADED_VALUES)} NOT NULL"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.execute("DELETE FROM model_research_artifacts WHERE artifact_type = 'random_ticket'")
        op.execute(
            "ALTER TABLE model_research_artifacts "
            f"MODIFY artifact_type {_enum_sql(DOWNGRADED_VALUES)} NOT NULL"
        )

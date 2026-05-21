"""add running to scrape_logs.status enum

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-21 16:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE scrape_logs MODIFY COLUMN status "
        "ENUM('running','success','failed','partial') NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE scrape_logs MODIFY COLUMN status "
        "ENUM('success','failed','partial') NOT NULL"
    )

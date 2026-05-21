"""fix UTC timestamps → Beijing time (+8h)

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-23 14:00:00.000000

All Python-originated timestamps were stored using ``datetime.utcnow()``
while the MySQL server time-zone is ``+08:00``.  This migration adds 8
hours to every affected column so that stored values match the DB
time-zone convention.

Affected tables / columns:
  - scrape_logs.started_at, scrape_logs.finished_at
  - sporttery_match_odds.scraped_at
  - sporttery_match_team_stats.scraped_at

``created_at`` / ``updated_at`` from ``TimestampMixin`` are NOT touched
because they use MySQL ``NOW()`` via ``server_default=func.now()`` and
were always correct.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FIXES = [
    ("scrape_logs", "started_at"),
    ("scrape_logs", "finished_at"),
    ("sporttery_match_odds", "scraped_at"),
    ("sporttery_match_team_stats", "scraped_at"),
]


def upgrade() -> None:
    for table, col in FIXES:
        op.execute(
            f"UPDATE `{table}` SET `{col}` = DATE_ADD(`{col}`, INTERVAL 8 HOUR) "
            f"WHERE `{col}` IS NOT NULL"
        )


def downgrade() -> None:
    for table, col in FIXES:
        op.execute(
            f"UPDATE `{table}` SET `{col}` = DATE_SUB(`{col}`, INTERVAL 8 HOUR) "
            f"WHERE `{col}` IS NOT NULL"
        )

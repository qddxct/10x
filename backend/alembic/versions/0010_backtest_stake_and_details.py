"""add fixed_stake & bets_detail to backtest_sessions

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-23 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "backtest_sessions",
        sa.Column(
            "fixed_stake",
            sa.DECIMAL(14, 2),
            nullable=True,
            comment="每场固定投注金额(CNY)",
        ),
    )
    op.add_column(
        "backtest_sessions",
        sa.Column(
            "bets_detail",
            sa.JSON(),
            nullable=True,
            comment="每场下注明细 JSON 快照",
        ),
    )


def downgrade() -> None:
    op.drop_column("backtest_sessions", "bets_detail")
    op.drop_column("backtest_sessions", "fixed_stake")

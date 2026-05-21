"""extend backtest_sessions with kelly/mode/equity_curve fields

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-21 19:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "backtest_sessions",
        sa.Column("equity_curve", sa.JSON(), nullable=True),
    )
    op.add_column(
        "backtest_sessions",
        sa.Column(
            "mode",
            sa.Enum("fixed", "kelly", "both", name="backtest_mode"),
            nullable=False,
            server_default="both",
        ),
    )
    op.add_column(
        "backtest_sessions",
        sa.Column("initial_capital", sa.DECIMAL(14, 2), nullable=True),
    )
    op.add_column(
        "backtest_sessions",
        sa.Column(
            "kelly_profit_loss",
            sa.DECIMAL(14, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "backtest_sessions",
        sa.Column(
            "kelly_roi",
            sa.DECIMAL(8, 4),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("backtest_sessions", "kelly_roi")
    op.drop_column("backtest_sessions", "kelly_profit_loss")
    op.drop_column("backtest_sessions", "initial_capital")
    op.drop_column("backtest_sessions", "mode")
    op.drop_column("backtest_sessions", "equity_curve")
    sa.Enum(name="backtest_mode").drop(op.get_bind(), checkfirst=True)

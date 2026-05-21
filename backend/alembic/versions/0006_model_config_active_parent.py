"""Add model_configs.is_active + parent_id; seed default as active.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-21 21:00:00.000000

P7 T1: introduce a globally-unique active pointer and clone lineage for
ModelConfig so the Dashboard / Scheduler / default scoring can pick a
canonical version while /backtest remains free to pick any historical
config. Also marks the existing ``name='default'`` row as active so fresh
installs and upgrades both converge on the same baseline.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_configs",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "model_configs",
        sa.Column("parent_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_model_configs_parent_id",
        "model_configs",
        "model_configs",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_model_configs_is_active",
        "model_configs",
        ["is_active"],
    )

    conn = op.get_bind()
    default_id = conn.execute(
        sa.text("SELECT id FROM model_configs WHERE name = 'default' ORDER BY id LIMIT 1")
    ).scalar()
    if default_id is not None:
        conn.execute(
            sa.text(
                "UPDATE model_configs SET is_active = :t WHERE id = :id"
            ),
            {"t": True, "id": default_id},
        )


def downgrade() -> None:
    op.drop_index("ix_model_configs_is_active", table_name="model_configs")
    op.drop_constraint(
        "fk_model_configs_parent_id", "model_configs", type_="foreignkey"
    )
    op.drop_column("model_configs", "parent_id")
    op.drop_column("model_configs", "is_active")

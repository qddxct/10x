"""add model research run/artifact tables

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-26 14:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_research_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=96), nullable=False),
        sa.Column("base_model_config_id", sa.Integer(), nullable=True),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=False),
        sa.Column("random_trials", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("running", "succeeded", "failed", name="model_research_status"),
            nullable=False,
            server_default="running",
        ),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("report_path", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["base_model_config_id"], ["model_configs.id"], ondelete="SET NULL"),
        comment="模型研究运行记录",
    )
    op.create_index("ix_model_research_runs_name", "model_research_runs", ["name"])
    op.create_index("ix_model_research_runs_created_at", "model_research_runs", ["created_at"])

    op.create_table(
        "model_research_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column(
            "artifact_type",
            sa.Enum(
                "factor_bucket",
                "combo_simulation",
                "random_baseline",
                "window_summary",
                "markdown_report",
                name="model_research_artifact_type",
            ),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["model_research_runs.id"], ondelete="CASCADE"),
        comment="模型研究结构化产物",
    )
    op.create_index("ix_model_research_artifacts_run_type", "model_research_artifacts", ["run_id", "artifact_type"])


def downgrade() -> None:
    op.drop_index("ix_model_research_artifacts_run_type", table_name="model_research_artifacts")
    op.drop_table("model_research_artifacts")
    op.drop_index("ix_model_research_runs_created_at", table_name="model_research_runs")
    op.drop_index("ix_model_research_runs_name", table_name="model_research_runs")
    op.drop_table("model_research_runs")
    sa.Enum(name="model_research_artifact_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="model_research_status").drop(op.get_bind(), checkfirst=True)

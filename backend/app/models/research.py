from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Date, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.model_config import ModelConfig


class ModelResearchRun(Base, TimestampMixin):
    """模型研究运行记录。"""

    __tablename__ = "model_research_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    base_model_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    random_trials: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("running", "succeeded", "failed", name="model_research_status"),
        nullable=False,
        default="running",
    )
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    base_model_config: Mapped[ModelConfig | None] = relationship()
    artifacts: Mapped[list[ModelResearchArtifact]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ModelResearchArtifact(Base):
    """模型研究结构化产物。"""

    __tablename__ = "model_research_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("model_research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(
        Enum(
            "factor_bucket",
            "combo_simulation",
            "random_baseline",
            "combo_ticket",
            "random_ticket",
            "window_summary",
            "markdown_report",
            name="model_research_artifact_type",
        ),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    run: Mapped[ModelResearchRun] = relationship(back_populates="artifacts")

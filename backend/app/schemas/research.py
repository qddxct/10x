from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResearchRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_model_config_id: int | None
    date_from: date
    date_to: date
    random_seed: int
    random_trials: int
    status: str
    summary_json: dict[str, Any] | None = None
    report_path: str | None = None
    created_at: datetime | None = None


class ResearchArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    artifact_type: str
    label: str
    payload_json: dict[str, Any]


class ResearchRunDetailRead(ResearchRunRead):
    artifacts: dict[str, list[ResearchArtifactRead]]


class ResearchGenerateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    date_from: date
    date_to: date
    model_name: str = "empirical-v32-filtered-candidate"
    random_trials: int = Field(default=1000, ge=100, le=5000)
    random_seed: int = Field(default=20260426, ge=1, le=999999999)


class ResearchScoreSummaryRead(BaseModel):
    rows: int
    candidates: int
    portfolio: int
    scored_matches: int
    recommended_scores: int
    draw_scores: int
    handicap_draw_scores: int
    replaced_old_scores: int


class ResearchGenerateResponse(BaseModel):
    run_id: int
    report_path: str
    score_summary: ResearchScoreSummaryRead
    research_summary: dict[str, Any]


class ResearchTicketRead(BaseModel):
    strategy: str
    ticket_date: str
    combo_odds: float
    stake: float | None = None
    is_hit: bool
    pnl: float
    group_type: str | None = None
    control_label: str | None = None
    legs: list[dict[str, Any]]


class ResearchTicketGroupSummaryRead(BaseModel):
    ticket_count: int
    stake: float
    returns: float
    pnl: float
    roi: float
    max_hit_streak: int
    max_miss_streak: int


class ResearchTicketGroupRead(BaseModel):
    group_key: str
    title: str
    description: str
    summary: ResearchTicketGroupSummaryRead
    tickets: list[ResearchTicketRead]

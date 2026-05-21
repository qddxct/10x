from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BetType = Literal["draw", "handicap_draw"]


class ScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    match_id: int
    model_config_id: int
    user_id: int | None = None

    euro_score: int
    asian_score: int
    goals_score: int
    intent_score: int
    compression_score: int
    team_stats_score: int
    total_score: int

    bet_type: BetType | None = None
    kelly_pct: Decimal | None = None
    is_recommended: bool

    actual_hit: bool | None = None
    bet_amount: Decimal | None = None
    notes: str | None = None

    match_date: datetime | None = None
    home_team: str | None = None
    away_team: str | None = None
    league_name: str | None = None
    match_round: str | None = None
    sporttery_match_id: str | None = None
    sporttery_url: str | None = None
    had_draw_odds: Decimal | None = None
    hhad_draw_odds: Decimal | None = None
    bet_odds: Decimal | None = None

    score_mode: Literal["rule", "diagnostic"] | None = None
    rule_name: str | None = None
    rule_score: int | None = None
    diagnostic_score: int | None = None
    rule_explanation: str | None = None


class ScoreListResponse(BaseModel):
    items: list[ScoreOut]
    total: int


class ScoreBreakdownItem(BaseModel):
    dimension: str
    score: int
    max_score: int
    explanation: str


class ScoreBreakdown(BaseModel):
    score: ScoreOut
    parts: list[ScoreBreakdownItem]


class ScoreUpdate(BaseModel):
    notes: str | None = None
    bet_amount: Decimal | None = Field(default=None, ge=0)
    actual_hit: bool | None = None


class ScoreComputeResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    date: date
    model_config_id: int
    computed: int
    skipped: int


class ScoreComputeUpcomingResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_config_id: int
    dates: list[date]
    computed: int
    skipped: int

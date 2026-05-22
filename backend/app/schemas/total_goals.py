from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TotalGoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    model_version: str
    target_goals: int
    target_label: str
    odds_label: str | None = None
    total_score: int
    confidence_pct: Decimal | None = None
    bet_odds: Decimal | None = None
    is_recommended: bool
    hit: bool | None = None
    explanation: dict | None = None

    match_date: datetime | None = None
    home_team: str | None = None
    away_team: str | None = None
    league_name: str | None = None
    match_round: str | None = None
    sporttery_url: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    actual_total_goals: int | None = None


class TotalGoalListResponse(BaseModel):
    items: list[TotalGoalOut]
    total: int


class TotalGoalCombo(BaseModel):
    title: str
    items: list[TotalGoalOut]
    combo_odds: Decimal | None = None
    avg_score: int
    status: str
    hit: bool | None = None


class TotalGoalTodayResponse(BaseModel):
    items: list[TotalGoalOut]
    total: int
    combos: list[TotalGoalCombo]


class TotalGoalComputeResult(BaseModel):
    date: date
    computed: int
    skipped: int


class TotalGoalComputeUpcomingResult(BaseModel):
    dates: list[date]
    computed: int
    skipped: int

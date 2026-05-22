from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ComboLegOut(BaseModel):
    score_id: int
    match_id: int
    match_round: str | None = None
    match_date: datetime | None = None
    league_name: str | None = None
    home_team: str
    away_team: str
    bet_type: str | None = None
    bet_odds: Decimal | None = None
    total_score: int
    sporttery_url: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    result: str | None = None
    handicap_result: str | None = None
    hit: bool | None = None


class ComboRecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    recommendation_date: date
    model_config_id: int
    model_name: str | None = None
    rank: int
    title: str
    combo_odds: Decimal | None = None
    avg_score: int
    status: str
    hit: bool | None = None
    created_at: datetime
    legs: list[ComboLegOut]


class ComboRecommendationListResponse(BaseModel):
    items: list[ComboRecommendationOut]
    total: int


class ComboSnapshotResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_config_id: int
    recommendation_date: date
    created: int
    items: list[ComboRecommendationOut]

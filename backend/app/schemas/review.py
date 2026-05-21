from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ReviewUpdate(BaseModel):
    actual_hit: bool | None = None
    bet_amount: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    expected_updated_at: datetime | None = Field(
        default=None,
        description=(
            "Optional optimistic lock: pass the row's updated_at as-read; "
            "if it has changed on the server, the request returns 409."
        ),
    )


class ReviewItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    score_id: int
    match_id: int
    match_date: datetime
    match_round: str | None = None
    sporttery_match_id: str | None = None
    sporttery_url: str | None = None
    league_name: str | None
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    result: str | None
    handicap_result: str | None

    total_score: int
    bet_type: str | None
    bet_odds: Decimal | None = None
    kelly_pct: Decimal | None
    is_recommended: bool

    actual_hit: bool | None
    suggested_actual_hit: bool | None
    bet_amount: Decimal | None
    notes: str | None

    model_config_id: int
    model_name: str | None = None
    user_id: int | None
    updated_at: datetime


class ReviewListResponse(BaseModel):
    items: list[ReviewItem]
    total: int


class ReviewQueryParams(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    only_recommended: bool = False

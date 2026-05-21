from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

BacktestMode = Literal["fixed", "kelly", "both"]


class BacktestCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_config_id: int | None = None
    date_from: date
    date_to: date
    mode: BacktestMode = "both"
    initial_capital: Decimal = Field(default=Decimal("10000"), ge=0)
    fixed_stake: Decimal = Field(default=Decimal("100"), ge=Decimal("0.01"))


class BacktestSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    model_config_id: int
    date_from: date
    date_to: date
    total_bets: int
    hit_count: int
    hit_rate: Decimal
    roi: Decimal
    profit_loss: Decimal
    kelly_profit_loss: Decimal
    kelly_roi: Decimal
    mode: str
    initial_capital: Decimal | None = None
    fixed_stake: Decimal | None = None
    bets_detail: list[dict[str, Any]] | None = None
    results_by_score: dict[str, Any] | None = None
    results_by_league: dict[str, Any] | None = None
    equity_curve: list[dict[str, Any]] | None = None
    created_at: datetime | None = None


class BacktestListResponse(BaseModel):
    items: list[BacktestSummary]
    total: int


class BacktestCompareResponse(BaseModel):
    a: BacktestSummary
    b: BacktestSummary

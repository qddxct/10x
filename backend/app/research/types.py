from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

BetType = Literal["draw", "handicap_draw"]
ComboStrategy = Literal["same_day_strongest", "two_day_rolling", "high_odds_attractor"]


@dataclass(frozen=True)
class ResearchCandidate:
    match_id: int
    match_date: date
    league: str
    home_team: str
    away_team: str
    bet_type: BetType
    odds: float
    is_hit: bool
    total_score: int
    handicap_value: float | None
    had_d: float | None
    hhad_d: float | None
    abs_hcap: float | None
    rank_gap: float | None
    recent_draw_sum: float | None
    recent_low_scoring_sum: float | None
    h2h_draw_rate: float | None
    h2h_one_goal_margin_rate: float | None
    home_recent_goal_diff: float | None
    away_recent_goal_diff: float | None
    result_label: str | None = None


@dataclass(frozen=True)
class ComboTicket:
    strategy: ComboStrategy
    ticket_date: date
    legs: tuple[ResearchCandidate, ResearchCandidate]
    combo_odds: float
    is_hit: bool
    pnl: float

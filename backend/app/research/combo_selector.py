from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from itertools import combinations
from typing import Literal

from app.research.types import ComboTicket, ResearchCandidate

SelectorStrategy = Literal[
    "balanced_selector",
    "conservative_selector",
    "frequency_selector",
]

PROFILE_ODDS_RANGE = {
    "balanced": (9.0, 14.0),
    "conservative": (9.0, 12.8),
    "frequency": (10.0, 14.0),
}

NEGATIVE_LEAGUES = {"德甲", "澳超"}
CONSERVATIVE_NEGATIVE_LEAGUES = {"德甲", "日职", "澳超", "挪超"}


def _combo_odds(a: ResearchCandidate, b: ResearchCandidate) -> float:
    return round(a.odds * b.odds, 4)


def _leg_score(candidate: ResearchCandidate, *, profile: str) -> float:
    score = float(candidate.total_score)
    if candidate.bet_type == "handicap_draw":
        score += 4.0 if profile != "conservative" else 2.0
    bad_leagues = CONSERVATIVE_NEGATIVE_LEAGUES if profile == "conservative" else NEGATIVE_LEAGUES
    if candidate.league in bad_leagues:
        score -= 7.0 if profile == "conservative" else 8.0
    if 3.1 <= candidate.odds <= 3.65:
        score += 2.0
    elif candidate.odds > 3.8:
        score -= 4.0
    return score


def score_pair(
    a: ResearchCandidate,
    b: ResearchCandidate,
    *,
    profile: Literal["balanced", "conservative", "frequency"] = "balanced",
) -> float | None:
    odds = _combo_odds(a, b)
    low, high = PROFILE_ODDS_RANGE[profile]
    if odds < low or odds > high:
        return None

    score = _leg_score(a, profile=profile) + _leg_score(b, profile=profile)

    if a.league != b.league:
        score += 8.0
    else:
        score -= 8.0

    if a.bet_type != b.bet_type:
        score += 0.0 if profile == "frequency" else 6.0
    elif a.bet_type == "draw":
        score -= 4.0

    if profile == "conservative":
        if a.league in CONSERVATIVE_NEGATIVE_LEAGUES and b.league in CONSERVATIVE_NEGATIVE_LEAGUES:
            return None
        if odds > 12.8:
            return None

    if profile == "frequency":
        score += min(odds, 14.0) * 0.5

    return score


def _ticket(
    strategy: SelectorStrategy,
    ticket_date: date,
    a: ResearchCandidate,
    b: ResearchCandidate,
) -> ComboTicket:
    odds = _combo_odds(a, b)
    hit = a.is_hit and b.is_hit
    pnl = round((odds - 1) * 100.0 if hit else -100.0, 4)
    return ComboTicket(
        strategy="same_day_strongest",
        ticket_date=ticket_date,
        legs=(a, b),
        combo_odds=odds,
        is_hit=hit,
        pnl=pnl,
    )


def _best_pair(
    candidates: list[ResearchCandidate],
    *,
    profile: Literal["balanced", "conservative", "frequency"],
) -> tuple[ResearchCandidate, ResearchCandidate] | None:
    best: tuple[float, ResearchCandidate, ResearchCandidate] | None = None
    for a, b in combinations(candidates, 2):
        score = score_pair(a, b, profile=profile)
        if score is None:
            continue
        if best is None or score > best[0]:
            best = (score, a, b)
    return None if best is None else (best[1], best[2])


def _by_date(candidates: list[ResearchCandidate]) -> dict[date, list[ResearchCandidate]]:
    grouped: dict[date, list[ResearchCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.match_date].append(candidate)
    return grouped


def select_combo_tickets(
    candidates: list[ResearchCandidate],
    *,
    strategy: SelectorStrategy,
) -> list[ComboTicket]:
    grouped = _by_date(candidates)
    tickets: list[ComboTicket] = []
    used: set[int] = set()
    profile: Literal["balanced", "conservative", "frequency"] = (
        "conservative"
        if strategy == "conservative_selector"
        else "frequency"
        if strategy == "frequency_selector"
        else "balanced"
    )

    for day in sorted(grouped):
        window = grouped[day]
        if strategy in {"balanced_selector", "frequency_selector"}:
            window = window + grouped.get(day + timedelta(days=1), [])
        window = [candidate for candidate in window if candidate.match_id not in used]
        pair = _best_pair(window, profile=profile)
        if pair is None:
            continue
        used.update({pair[0].match_id, pair[1].match_id})
        tickets.append(_ticket(strategy, day, pair[0], pair[1]))
    return tickets

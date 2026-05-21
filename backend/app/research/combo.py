from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from app.research.metrics import max_losing_streak, summarize_returns
from app.research.types import ComboStrategy, ComboTicket, ResearchCandidate


def _strength(
    candidate: ResearchCandidate, *, high_odds: bool = False
) -> tuple[float, float, float]:
    type_bonus = 8.0 if candidate.bet_type == "handicap_draw" else 0.0
    odds_bonus = candidate.odds if high_odds else 0.0
    return (candidate.total_score + type_bonus, odds_bonus, candidate.odds)


def _best_pair(
    candidates: list[ResearchCandidate], *, high_odds: bool
) -> tuple[ResearchCandidate, ResearchCandidate] | None:
    if len(candidates) < 2:
        return None
    ordered = sorted(candidates, key=lambda c: _strength(c, high_odds=high_odds), reverse=True)
    return ordered[0], ordered[1]


def _ticket(
    strategy: ComboStrategy,
    ticket_date: date,
    a: ResearchCandidate,
    b: ResearchCandidate,
    *,
    stake: float,
) -> ComboTicket:
    combo_odds = round(a.odds * b.odds, 4)
    hit = a.is_hit and b.is_hit
    pnl = round((combo_odds - 1) * stake if hit else -stake, 4)
    return ComboTicket(
        strategy=strategy,
        ticket_date=ticket_date,
        legs=(a, b),
        combo_odds=combo_odds,
        is_hit=hit,
        pnl=pnl,
    )


def simulate_combo_strategy(
    candidates: list[ResearchCandidate],
    *,
    strategy: ComboStrategy,
    stake: float = 100.0,
) -> list[ComboTicket]:
    by_date: dict[date, list[ResearchCandidate]] = defaultdict(list)
    for candidate in candidates:
        by_date[candidate.match_date].append(candidate)

    tickets: list[ComboTicket] = []
    used_match_ids: set[int] = set()
    high_odds = strategy == "high_odds_attractor"

    if strategy in {"same_day_strongest", "high_odds_attractor"}:
        for day in sorted(by_date):
            day_candidates = by_date[day]
            if strategy == "high_odds_attractor":
                day_candidates = [c for c in day_candidates if c.total_score >= 108]
                day_candidates = sorted(
                    day_candidates, key=lambda c: (c.odds, c.total_score), reverse=True
                )
                pair = (day_candidates[0], day_candidates[1]) if len(day_candidates) >= 2 else None
            else:
                pair = _best_pair(day_candidates, high_odds=high_odds)
            if pair is not None:
                tickets.append(_ticket(strategy, day, pair[0], pair[1], stake=stake))
        return tickets

    if strategy == "two_day_rolling":
        for day in sorted(by_date):
            window = [
                c
                for c in by_date.get(day, []) + by_date.get(day + timedelta(days=1), [])
                if c.match_id not in used_match_ids
            ]
            pair = _best_pair(window, high_odds=False)
            if pair is None:
                continue
            used_match_ids.update({pair[0].match_id, pair[1].match_id})
            tickets.append(_ticket(strategy, day, pair[0], pair[1], stake=stake))
        return tickets

    raise ValueError(f"unsupported combo strategy: {strategy}")


def summarize_combo_tickets(
    tickets: list[ComboTicket], *, total_days: int, stake: float = 100.0
) -> dict:
    pnls = [ticket.pnl for ticket in tickets]
    summary = summarize_returns(pnls, stake=stake)
    combo_odds = [ticket.combo_odds for ticket in tickets]
    active_days = len({ticket.ticket_date for ticket in tickets})
    return {
        "combo_count": summary["bets"],
        "hit_count": summary["hits"],
        "hit_rate": summary["hit_rate"],
        "roi": summary["roi"],
        "pnl": summary["pnl"],
        "avg_combo_odds": sum(combo_odds) / len(combo_odds) if combo_odds else 0.0,
        "median_combo_odds": sorted(combo_odds)[len(combo_odds) // 2] if combo_odds else 0.0,
        "active_days": active_days,
        "coverage_rate": active_days / total_days if total_days else 0.0,
        "max_losing_streak": max_losing_streak([ticket.is_hit for ticket in tickets]),
    }

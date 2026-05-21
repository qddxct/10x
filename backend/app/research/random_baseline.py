from __future__ import annotations

import random

from app.research.combo import summarize_combo_tickets
from app.research.metrics import percentile_rank, quantile
from app.research.types import ComboTicket, ResearchCandidate


def _random_ticket_pair(
    rng: random.Random, candidates: list[ResearchCandidate], *, stake: float
) -> ComboTicket | None:
    if len(candidates) < 2:
        return None
    a, b = rng.sample(candidates, 2)
    combo_odds = round(a.odds * b.odds, 4)
    hit = a.is_hit and b.is_hit
    pnl = round((combo_odds - 1) * stake if hit else -stake, 4)
    return ComboTicket(
        strategy="same_day_strongest",
        ticket_date=min(a.match_date, b.match_date),
        legs=(a, b),
        combo_odds=combo_odds,
        is_hit=hit,
        pnl=pnl,
    )


def run_random_combo_baseline(
    market_candidates: list[ResearchCandidate],
    *,
    ticket_count: int,
    trials: int,
    seed: int,
    model_roi: float | None = None,
    stake: float = 100.0,
) -> dict:
    rng = random.Random(seed)
    rois: list[float] = []
    max_losing_streaks: list[int] = []
    for _ in range(trials):
        tickets = []
        for _idx in range(ticket_count):
            ticket = _random_ticket_pair(rng, market_candidates, stake=stake)
            if ticket is not None:
                tickets.append(ticket)
        summary = summarize_combo_tickets(tickets, total_days=max(1, ticket_count), stake=stake)
        rois.append(float(summary["roi"]))
        max_losing_streaks.append(int(summary["max_losing_streak"]))

    return {
        "trials": trials,
        "ticket_count": ticket_count,
        "roi_avg": sum(rois) / len(rois) if rois else 0.0,
        "roi_median": quantile(rois, 0.5),
        "roi_p80": quantile(rois, 0.8),
        "roi_p90": quantile(rois, 0.9),
        "roi_p95": quantile(rois, 0.95),
        "max_losing_streak_avg": sum(max_losing_streaks) / len(max_losing_streaks)
        if max_losing_streaks
        else 0.0,
        "model_roi_percentile": percentile_rank(model_roi, rois) if model_roi is not None else None,
    }


def sample_random_combo_tickets(
    market_candidates: list[ResearchCandidate],
    *,
    ticket_count: int,
    seed: int,
    stake: float = 100.0,
) -> list[ComboTicket]:
    """Generate one deterministic random-control ticket sample for audit display."""
    rng = random.Random(seed)
    tickets: list[ComboTicket] = []
    for _idx in range(ticket_count):
        ticket = _random_ticket_pair(rng, market_candidates, stake=stake)
        if ticket is not None:
            tickets.append(
                ComboTicket(
                    strategy="random_control",
                    ticket_date=ticket.ticket_date,
                    legs=ticket.legs,
                    combo_odds=ticket.combo_odds,
                    is_hit=ticket.is_hit,
                    pnl=ticket.pnl,
                )
            )
    return tickets

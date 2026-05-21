from datetime import date, timedelta

from app.research.combo import simulate_combo_strategy, summarize_combo_tickets
from app.research.types import ResearchCandidate


def _candidate(match_id: int, day: date, *, bet_type="draw", odds=3.0, hit=True, score=108):
    return ResearchCandidate(
        match_id=match_id,
        match_date=day,
        league="英超",
        home_team=f"H{match_id}",
        away_team=f"A{match_id}",
        bet_type=bet_type,
        odds=odds,
        is_hit=hit,
        total_score=score,
        handicap_value=1.0 if bet_type == "handicap_draw" else 0.25,
        had_d=odds if bet_type == "draw" else None,
        hhad_d=odds if bet_type == "handicap_draw" else None,
        abs_hcap=0.25,
        rank_gap=5,
        recent_draw_sum=0.6,
        recent_low_scoring_sum=1.2,
        h2h_draw_rate=0.4,
        h2h_one_goal_margin_rate=0.4,
        home_recent_goal_diff=1,
        away_recent_goal_diff=-1,
    )


def test_same_day_strongest_builds_one_ticket_per_day():
    day = date(2026, 4, 1)
    tickets = simulate_combo_strategy(
        [
            _candidate(1, day, odds=3.0),
            _candidate(2, day, odds=3.5, hit=False, score=100),
            _candidate(3, day, odds=3.2, score=110),
        ],
        strategy="same_day_strongest",
    )
    assert len(tickets) == 1
    assert tickets[0].combo_odds == 9.6
    assert tickets[0].is_hit is True
    assert tickets[0].pnl == 860.0


def test_two_day_rolling_pairs_across_adjacent_days():
    day = date(2026, 4, 1)
    tickets = simulate_combo_strategy(
        [_candidate(1, day), _candidate(2, day + timedelta(days=1))],
        strategy="two_day_rolling",
    )
    assert len(tickets) == 1
    assert tickets[0].ticket_date == day


def test_summarize_combo_tickets_reports_frequency():
    day = date(2026, 4, 1)
    tickets = simulate_combo_strategy(
        [_candidate(1, day), _candidate(2, day)], strategy="same_day_strongest"
    )
    summary = summarize_combo_tickets(tickets, total_days=10)
    assert summary["combo_count"] == 1
    assert summary["coverage_rate"] == 0.1

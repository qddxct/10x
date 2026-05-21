from datetime import date

from app.research.random_baseline import run_random_combo_baseline, sample_random_combo_tickets
from app.research.types import ResearchCandidate


def _candidate(match_id: int, odds: float, hit: bool):
    return ResearchCandidate(
        match_id=match_id,
        match_date=date(2026, 4, 1 + match_id % 2),
        league="英超",
        home_team=f"H{match_id}",
        away_team=f"A{match_id}",
        bet_type="draw",
        odds=odds,
        is_hit=hit,
        total_score=108,
        handicap_value=0.25,
        had_d=odds,
        hhad_d=None,
        abs_hcap=0.25,
        rank_gap=5,
        recent_draw_sum=0.6,
        recent_low_scoring_sum=1.2,
        h2h_draw_rate=0.4,
        h2h_one_goal_margin_rate=0.4,
        home_recent_goal_diff=1,
        away_recent_goal_diff=-1,
    )


def test_random_baseline_is_reproducible():
    market = [_candidate(i, 3.0 + i * 0.01, i % 3 == 0) for i in range(1, 20)]
    a = run_random_combo_baseline(market, ticket_count=5, trials=20, seed=7)
    b = run_random_combo_baseline(market, ticket_count=5, trials=20, seed=7)
    assert a == b
    assert a["trials"] == 20
    assert "roi_p90" in a


def test_random_baseline_reports_model_percentile():
    market = [_candidate(i, 3.0, i % 2 == 0) for i in range(1, 20)]
    result = run_random_combo_baseline(market, ticket_count=4, trials=10, seed=1, model_roi=0.5)
    assert 0 <= result["model_roi_percentile"] <= 1


def test_sample_random_combo_tickets_is_reproducible_and_auditable():
    market = [_candidate(i, 3.0 + i * 0.01, i % 3 == 0) for i in range(1, 20)]

    a = sample_random_combo_tickets(market, ticket_count=3, seed=9)
    b = sample_random_combo_tickets(market, ticket_count=3, seed=9)

    assert a == b
    assert len(a) == 3
    assert all(len(ticket.legs) == 2 for ticket in a)
    assert all(ticket.strategy == "random_control" for ticket in a)

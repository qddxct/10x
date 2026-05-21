from datetime import date

from app.research.factors import build_factor_buckets
from app.research.types import ResearchCandidate


def _candidate(**overrides):
    base = dict(
        match_id=1,
        match_date=date(2026, 4, 1),
        league="英超",
        home_team="A",
        away_team="B",
        bet_type="draw",
        odds=3.2,
        is_hit=True,
        total_score=108,
        handicap_value=0.25,
        had_d=3.2,
        hhad_d=None,
        abs_hcap=0.25,
        rank_gap=3,
        recent_draw_sum=0.6,
        recent_low_scoring_sum=1.2,
        h2h_draw_rate=0.4,
        h2h_one_goal_margin_rate=0.5,
        home_recent_goal_diff=2,
        away_recent_goal_diff=-1,
    )
    base.update(overrides)
    return ResearchCandidate(**base)


def test_build_factor_buckets_splits_draw_odds_ranges():
    rows = [
        _candidate(match_id=1, odds=3.2, had_d=3.2, is_hit=True),
        _candidate(match_id=2, odds=3.55, had_d=3.55, is_hit=False),
    ]
    buckets = build_factor_buckets(rows)
    by_label = {b["label"]: b for b in buckets if b["factor"] == "draw_odds_range"}
    assert by_label["3.10-3.29"]["bets"] == 1
    assert by_label["3.10-3.29"]["roi"] == 2.2
    assert by_label["3.50+"]["bets"] == 1
    assert by_label["3.50+"]["roi"] == -1.0


def test_build_factor_buckets_marks_small_sample_observational():
    buckets = build_factor_buckets([_candidate(match_id=1)])
    first = next(b for b in buckets if b["factor"] == "league")
    assert first["sample_note"] == "观察样本"

from __future__ import annotations

import pytest
from app.engine.kelly import kelly_pct, suggest_bet_type

BANDS = {
    "low": {"min_score": 78, "max_score": 84, "kelly_pct": 0.01},
    "mid": {"min_score": 84, "max_score": 96, "kelly_pct": 0.015},
    "high": {"min_score": 96, "max_score": 120, "kelly_pct": 0.02},
}


@pytest.mark.parametrize(
    "score,expected",
    [
        (50, 0.0),
        (77, 0.0),
        (78, 0.01),
        (83, 0.01),
        (84, 0.015),
        (95, 0.015),
        (96, 0.02),
        (120, 0.02),
    ],
)
def test_kelly_pct_buckets(score, expected):
    assert kelly_pct(score, BANDS) == pytest.approx(expected)


def test_kelly_pct_empty_bands_returns_zero():
    assert kelly_pct(100, {}) == 0.0


@pytest.mark.parametrize(
    "asian,draw_odds,hcap_draw_odds,score,expected",
    [
        ("平手", 3.10, None, 90, "draw"),
        ("平半", 3.20, None, 85, "draw"),
        ("半球", None, 3.60, 80, "handicap_draw"),
        ("一球", None, 3.80, 90, "handicap_draw"),
        ("一球", None, 3.00, 90, None),
        ("半球", None, None, 90, None),
        ("平手", 3.10, None, 50, None),
    ],
)
def test_suggest_bet_type(asian, draw_odds, hcap_draw_odds, score, expected):
    assert (
        suggest_bet_type(
            asian_handicap=asian,
            draw_odds=draw_odds,
            handicap_draw_odds=hcap_draw_odds,
            total_score=score,
            min_draw_score=84,
            min_handicap_score=78,
        )
        == expected
    )


def test_suggest_bet_type_can_tighten_draw_to_level_ball_only():
    assert (
        suggest_bet_type(
            asian_handicap="0.25",
            draw_odds=3.20,
            handicap_draw_odds=None,
            total_score=110,
            min_draw_score=104,
            min_handicap_score=104,
            max_draw_handicap_abs=0.0,
        )
        is None
    )
    assert (
        suggest_bet_type(
            asian_handicap="0.00",
            draw_odds=3.10,
            handicap_draw_odds=None,
            total_score=110,
            min_draw_score=104,
            min_handicap_score=104,
            max_draw_handicap_abs=0.0,
        )
        == "draw"
    )

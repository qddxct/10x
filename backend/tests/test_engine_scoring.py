from __future__ import annotations

from decimal import Decimal

import pytest
from app.engine.scoring import (
    DEFAULT_WEIGHTS,
    asian_score,
    compression_score,
    empirical_draw_score,
    empirical_handicap_draw_score,
    euro_score,
    goals_score,
    infer_competition_type,
    intent_score,
    team_stats_score,
    total_score,
)


@pytest.mark.parametrize(
    "win,draw,lose,expected_min",
    [
        (Decimal("2.50"), Decimal("3.20"), Decimal("2.60"), 20),
        (Decimal("2.80"), Decimal("3.10"), Decimal("2.50"), 20),
        (Decimal("1.50"), Decimal("4.00"), Decimal("6.00"), 0),
    ],
)
def test_euro_score_three_way_closeness(win, draw, lose, expected_min):
    s = euro_score(win=win, draw=draw, lose=lose)
    assert 0 <= s <= 25
    assert s >= expected_min


def test_euro_score_returns_zero_when_missing():
    assert euro_score(win=None, draw=None, lose=None) == 0


@pytest.mark.parametrize(
    "handicap,expected",
    [
        ("平手", 20),
        ("平半", 15),
        ("半球", 5),
        ("一球", 0),
        (None, 0),
    ],
)
def test_asian_score_buckets(handicap, expected):
    assert asian_score(handicap) == expected


@pytest.mark.parametrize(
    "goals,expected",
    [
        (Decimal("2.00"), 20),
        (Decimal("2.25"), 20),
        (Decimal("2.5"), 10),
        (Decimal("2.75"), 0),
        (Decimal("3.0"), 0),
        (None, 0),
    ],
)
def test_goals_score_buckets(goals, expected):
    assert goals_score(goals) == expected


@pytest.mark.parametrize(
    "draw_odds,expected",
    [
        (Decimal("3.00"), 20),
        (Decimal("3.20"), 20),
        (Decimal("3.40"), 10),
        (Decimal("3.60"), 0),
        (None, 0),
    ],
)
def test_compression_score_buckets(draw_odds, expected):
    assert compression_score(draw_odds) == expected


@pytest.mark.parametrize(
    "ctype,rnd,expected",
    [
        ("cup", None, 15),
        ("knockout_first_leg", "首回合", 15),
        ("league", None, 5),
        (None, None, 5),
    ],
)
def test_intent_score(ctype, rnd, expected):
    assert intent_score(ctype, rnd) == expected


def test_team_stats_score_returns_zero_when_missing():
    assert team_stats_score(None) == 0


def test_team_stats_score_higher_for_close_ranks_and_balanced_form():
    stats = {
        "home_rank": 5,
        "away_rank": 6,
        "home_season_wins": 10,
        "home_season_draws": 8,
        "home_season_losses": 6,
        "away_season_wins": 9,
        "away_season_draws": 9,
        "away_season_losses": 7,
        "home_home_wins": 5,
        "home_home_draws": 4,
        "home_home_losses": 3,
        "away_away_wins": 4,
        "away_away_draws": 5,
        "away_away_losses": 4,
        "home_recent_form": "WDDLW",
        "away_recent_form": "DDWLL",
    }
    close = team_stats_score(stats)

    far_stats = {**stats, "home_rank": 1, "away_rank": 18}
    far = team_stats_score(far_stats)

    assert 0 <= close <= 20
    assert close > far


def test_empirical_draw_score_prefers_high_draw_tendency():
    high_draw_stats = {
        "home_rank": 4,
        "away_rank": 7,
        "home_season_wins": 6,
        "home_season_draws": 9,
        "home_season_losses": 5,
        "away_season_wins": 5,
        "away_season_draws": 8,
        "away_season_losses": 6,
        "home_home_wins": 2,
        "home_home_draws": 6,
        "home_home_losses": 2,
        "away_away_wins": 2,
        "away_away_draws": 6,
        "away_away_losses": 2,
        "home_recent_form": "DDWDL",
        "away_recent_form": "DWDDL",
    }
    low_draw_stats = {
        **high_draw_stats,
        "home_season_draws": 1,
        "away_season_draws": 1,
        "home_home_draws": 0,
        "away_away_draws": 0,
    }

    assert (
        empirical_draw_score(
            high_draw_stats,
            draw_odds=Decimal("3.10"),
            handicap_value=Decimal("0.00"),
            league_name="日职",
        )
        > empirical_draw_score(
            low_draw_stats,
            draw_odds=Decimal("3.10"),
            handicap_value=Decimal("0.00"),
            league_name="日职",
        )
    )


def test_empirical_handicap_draw_score_prefers_one_goal_margin_profile():
    low_draw_stats = {
        "home_rank": 2,
        "away_rank": 12,
        "home_season_wins": 12,
        "home_season_draws": 3,
        "home_season_losses": 5,
        "away_season_wins": 5,
        "away_season_draws": 4,
        "away_season_losses": 11,
        "home_home_wins": 7,
        "home_home_draws": 1,
        "home_home_losses": 2,
        "away_away_wins": 2,
        "away_away_draws": 2,
        "away_away_losses": 6,
        "home_recent_form": "WWDLW",
        "away_recent_form": "LDWDL",
    }
    high_draw_stats = {
        **low_draw_stats,
        "home_home_draws": 6,
        "away_away_draws": 6,
        "home_season_draws": 9,
        "away_season_draws": 9,
    }

    assert empirical_handicap_draw_score(
        low_draw_stats,
        handicap_value=Decimal("1.25"),
        draw_odds=Decimal("3.10"),
        handicap_draw_odds=Decimal("3.60"),
    ) > empirical_handicap_draw_score(
        high_draw_stats,
        handicap_value=Decimal("1.25"),
        draw_odds=Decimal("3.10"),
        handicap_draw_odds=Decimal("3.60"),
    )


@pytest.mark.parametrize(
    "league_name,round_text,expected",
    [
        ("欧冠", None, "cup"),
        ("欧联", None, "cup"),
        ("英超", None, "league"),
        ("意甲", "首回合", "knockout_first_leg"),
        ("意甲", "次回合", "knockout_second_leg"),
        (None, None, "league"),
    ],
)
def test_infer_competition_type(league_name, round_text, expected):
    assert infer_competition_type(league_name, round_text) == expected


def test_total_score_uses_default_weights_when_none_provided():
    parts = {
        "euro": 25,
        "asian": 20,
        "goals": 20,
        "intent": 15,
        "compression": 20,
        "team_stats": 20,
    }
    total = total_score(parts)
    assert total == 120
    assert total == sum(DEFAULT_WEIGHTS.values())


def test_total_score_respects_custom_weights():
    parts = {
        "euro": 25,
        "asian": 20,
        "goals": 20,
        "intent": 15,
        "compression": 20,
        "team_stats": 20,
    }
    weights = {
        "euro": 0.5,
        "asian": 0.5,
        "goals": 0.5,
        "intent": 0.5,
        "compression": 0.5,
        "team_stats": 0.5,
    }
    assert total_score(parts, weights=weights) == 60

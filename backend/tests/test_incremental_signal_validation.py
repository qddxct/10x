from __future__ import annotations

from datetime import date

from app.scripts.incremental_signal_validation import (
    bucket,
    bucket_summary,
    calculate_stats,
    data_gap_rows,
    draw_candidate_rules,
    enrich_row_features,
    goal_margin,
    hdraw_candidate_rules,
    is_hdraw_a,
    non_overlapping_windows,
    roi,
    safe_rate,
    window_summary,
)


def test_safe_rate_handles_missing_and_zero_denominator():
    assert safe_rate(None, 10) is None
    assert safe_rate(3, None) is None
    assert safe_rate(3, 0) is None
    assert safe_rate(3, 10) == 0.3


def test_goal_margin_returns_home_minus_away():
    assert goal_margin(2, 1) == 1
    assert goal_margin(1, 3) == -2


def test_roi_uses_fixed_100_unit_stake():
    assert roi([150.0, -100.0, -100.0]) == -50.0 / 300.0


def test_bucket_labels_edges():
    assert bucket(None, [0, 1, 2], ["0-1", "1-2", ">=2"]) == "NA"
    assert bucket(0.5, [0, 1, 2], ["0-1", "1-2", ">=2"]) == "0-1"
    assert bucket(1.5, [0, 1, 2], ["0-1", "1-2", ">=2"]) == "1-2"
    assert bucket(3, [0, 1, 2], ["0-1", "1-2", ">=2"]) == ">=2"


def test_calculate_stats_for_draw_channel():
    rows = [
        {"is_draw": True, "had_d": 3.2},
        {"is_draw": False, "had_d": 3.1},
        {"is_draw": True, "had_d": None},
    ]

    stats = calculate_stats(rows, target="draw")

    assert stats.bets == 2
    assert stats.hits == 1
    assert stats.hit_rate == 0.5
    assert round(stats.roi, 4) == 0.6000


def test_calculate_stats_for_handicap_draw_channel():
    rows = [
        {"is_hdraw": True, "hhad_d": 3.6},
        {"is_hdraw": False, "hhad_d": 3.4},
    ]

    stats = calculate_stats(rows, target="hdraw")

    assert stats.bets == 2
    assert stats.hits == 1
    assert round(stats.roi, 4) == 0.8000


def test_is_hdraw_a_matches_current_v3_rule():
    row = {
        "hcap": 1.25,
        "rank_gap": 8,
        "hhad_d": 3.6,
        "venue_draw_sum": 0.5,
        "season_draw_sum": 0.45,
    }

    assert is_hdraw_a(row) is True
    assert is_hdraw_a({**row, "rank_gap": 3}) is False
    assert is_hdraw_a({**row, "hhad_d": 3.4}) is False
    assert is_hdraw_a({**row, "hcap": 1.5}) is False
    assert is_hdraw_a({**row, "venue_draw_sum": 0.2}) is False


def test_enrich_row_features_computes_rates_and_margin():
    row = {
        "home_score": 2,
        "away_score": 1,
        "home_season_wins": 10,
        "home_season_draws": 5,
        "home_season_losses": 5,
        "away_season_wins": 6,
        "away_season_draws": 4,
        "away_season_losses": 10,
        "home_home_wins": 7,
        "home_home_draws": 2,
        "home_home_losses": 1,
        "away_away_wins": 2,
        "away_away_draws": 3,
        "away_away_losses": 5,
        "home_rank": 3,
        "away_rank": 12,
        "h2h_home_wins": 2,
        "h2h_draws": 1,
        "h2h_away_wins": 1,
        "home_recent_form": "WWDL",
        "away_recent_form": "LLDW",
        "home_recent_matches_count": 6,
        "home_recent_goals_for": 9,
        "home_recent_goals_against": 6,
        "home_recent_win_by_1": 2,
        "home_recent_low_scoring_count": 4,
        "away_recent_matches_count": 6,
        "away_recent_goals_for": 5,
        "away_recent_goals_against": 8,
        "away_recent_loss_by_1": 1,
        "away_recent_low_scoring_count": 3,
        "home_home_recent_matches_count": 3,
        "home_home_recent_win_by_1": 1,
        "away_away_recent_matches_count": 3,
        "away_away_recent_loss_by_1": 1,
        "h2h_matches_count": 4,
        "h2h_one_goal_margin_count": 2,
    }

    out = enrich_row_features(row)

    assert out["goal_margin"] == 1
    assert out["rank_gap"] == 9
    assert out["season_draw_sum"] == 0.45
    assert out["venue_draw_sum"] == 0.5
    assert out["h2h_draw_rate"] == 0.25
    assert out["home_recent_win_rate"] == 0.5
    assert out["away_recent_loss_rate"] == 0.5
    assert round(out["home_recent_win_by_1_rate"], 4) == 0.3333
    assert round(out["away_recent_loss_by_1_rate"], 4) == 0.1667
    assert out["home_recent_gf_per_match"] == 1.5
    assert round(out["away_recent_ga_per_match"], 4) == 1.3333
    assert round(out["home_home_recent_win_by_1_rate"], 4) == 0.3333
    assert round(out["away_away_recent_loss_by_1_rate"], 4) == 0.3333
    assert out["h2h_one_goal_margin_rate"] == 0.5
    assert round(out["recent_low_scoring_sum"], 4) == 1.1667


def test_data_gap_rows_reports_structured_recent_score_dimensions():
    rows = [
        {
            "home_recent_form": "WWDL",
            "h2h_draw_rate": 0.25,
            "home_recent_matches_count": 6,
            "home_recent_gf_per_match": 1.5,
            "home_recent_win_by_1_rate": 0.33,
        },
        {
            "home_recent_form": None,
            "h2h_draw_rate": None,
            "home_recent_matches_count": None,
            "home_recent_gf_per_match": None,
            "home_recent_win_by_1_rate": None,
        },
    ]

    gaps = data_gap_rows(rows)

    names = {row[0] for row in gaps}
    assert "recent_form_wdl" in names
    assert "h2h_wdl" in names
    assert "structured_recent_scores" in names
    assert "goals_for_against" in names
    assert "one_goal_margin_distribution" in names
    assert "odds_movement_history" in names


def test_bucket_summary_groups_rows_by_feature():
    rows = [
        {"league_group": "A", "is_hdraw": True, "hhad_d": 3.6},
        {"league_group": "A", "is_hdraw": False, "hhad_d": 3.6},
        {"league_group": "B", "is_hdraw": True, "hhad_d": 3.4},
    ]

    summary = bucket_summary(rows, key="league_group", target="hdraw", min_bets=1)

    assert {row[0] for row in summary} == {"A", "B"}


def test_non_overlapping_windows_covers_date_range():
    windows = non_overlapping_windows(date(2026, 1, 1), date(2026, 4, 10), days=90)

    assert windows == [
        (date(2026, 1, 1), date(2026, 3, 31)),
        (date(2026, 4, 1), date(2026, 4, 10)),
    ]


def test_window_summary_filters_rows_by_date():
    rows = [
        {"match_date": date(2026, 1, 1), "is_draw": True, "had_d": 3.2},
        {"match_date": date(2026, 4, 1), "is_draw": False, "had_d": 3.1},
    ]

    summary = window_summary(
        rows,
        target="draw",
        start=date(2026, 1, 1),
        end=date(2026, 3, 31),
    )

    assert summary.bets == 1
    assert summary.hits == 1


def test_hdraw_candidate_rules_include_hdraw_a_and_h2h_filters():
    names = [rule.name for rule in hdraw_candidate_rules()]

    assert "HDRAW_A 当前规则" in names
    assert "H2H 平局率 >= 0.35" in names
    assert "主队近期胜率 < 0.67" in names
    assert "主近一球胜 + 客近一球负" in names
    assert "客队近期失球 <= 1.60" in names


def test_draw_candidate_rules_include_shallow_and_balanced_markets():
    names = [rule.name for rule in draw_candidate_rules()]

    assert "浅盘口 <= 0.25" in names
    assert "澳门平赔 3.00-3.20" in names
    assert "排名差 <= 5" in names
    assert "低比分倾向和 >= 1.00" in names
    assert "H2H 一球差率 >= 0.35" in names

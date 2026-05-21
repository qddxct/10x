from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.scripts.v31_combination_candidate_backtest import (
    V32_CANDIDATE_MODEL_NAME,
    CandidateRule,
    calculate_stats,
    candidate_version,
    csv_lines,
    draw_rules,
    enrich_features,
    evaluate_rules,
    hdraw_rules,
    portfolio_rows,
    render_report,
    safe_rate,
    score_values_for_rule,
    v32_draw_rules,
    v32_hdraw_rules,
    window_ranges,
)


def test_candidate_rule_has_required_fields():
    rule = CandidateRule(
        name="DRAW_V31_TEST",
        channel="draw",
        bet_type="draw",
        priority=10,
        fn=lambda row: True,
    )

    assert rule.name == "DRAW_V31_TEST"
    assert rule.channel == "draw"
    assert rule.bet_type == "draw"
    assert rule.priority == 10
    assert rule.fn({}) is True


def test_draw_and_hdraw_rules_are_named_and_prioritized():
    assert [rule.name for rule in draw_rules()] == [
        "DRAW_V31_D",
        "DRAW_V31_A",
        "DRAW_V31_B",
        "DRAW_V31_C",
    ]
    assert [rule.name for rule in hdraw_rules()] == [
        "HDRAW_V31_A1",
        "HDRAW_V31_A2",
        "HDRAW_V31_A0",
        "HDRAW_V31_B",
        "HDRAW_V31_C",
    ]
    assert [rule.priority for rule in draw_rules()] == [100, 90, 80, 70]
    assert [rule.priority for rule in hdraw_rules()] == [100, 95, 90, 80, 70]


def test_calculate_stats_uses_fixed_100_stake():
    rows = [
        {"hit": True, "odds": 3.6},
        {"hit": False, "odds": 3.4},
    ]

    stats = calculate_stats(rows)

    assert stats.bets == 2
    assert stats.hits == 1
    assert stats.hit_rate == 0.5
    assert round(stats.roi, 4) == 0.8
    assert stats.pnl == 160.0


def test_safe_rate_handles_missing_and_zero():
    assert safe_rate(None, 6) is None
    assert safe_rate(1, None) is None
    assert safe_rate(1, 0) is None
    assert safe_rate(2, 4) == 0.5


def test_enrich_features_computes_v31_rates():
    row = {
        "home_rank": 4,
        "away_rank": 13,
        "home_season_draws": 5,
        "home_season_wins": 8,
        "home_season_losses": 7,
        "away_season_draws": 4,
        "away_season_wins": 6,
        "away_season_losses": 10,
        "home_home_draws": 3,
        "home_home_wins": 4,
        "home_home_losses": 3,
        "away_away_draws": 2,
        "away_away_wins": 3,
        "away_away_losses": 5,
        "home_recent_form": "WDDLLW",
        "away_recent_form": "LDLDWW",
        "h2h_draws": 2,
        "h2h_home_wins": 2,
        "h2h_away_wins": 1,
        "home_recent_matches_count": 6,
        "home_recent_win_by_1": 2,
        "home_recent_low_scoring_count": 4,
        "away_recent_matches_count": 6,
        "away_recent_loss_by_1": 1,
        "away_recent_loss_by_2plus": 2,
        "away_recent_goals_against": 9,
        "away_recent_low_scoring_count": 3,
        "h2h_matches_count": 5,
        "h2h_one_goal_margin_count": 3,
    }

    out = enrich_features(row)

    assert out["rank_gap"] == 9
    assert out["season_draw_sum"] == 0.45
    assert out["venue_draw_sum"] == 0.5
    assert round(out["recent_draw_sum"], 4) == 0.6667
    assert out["h2h_draw_rate"] == 0.4
    assert round(out["home_recent_win_by_1_rate"], 4) == 0.3333
    assert round(out["away_recent_loss_by_1_rate"], 4) == 0.1667
    assert out["away_recent_ga_per_match"] == 1.5
    assert round(out["away_recent_loss_by_2plus_rate"], 4) == 0.3333
    assert out["h2h_one_goal_margin_rate"] == 0.6
    assert round(out["recent_low_scoring_sum"], 4) == 1.1667


def test_draw_v31_rules_match_expected_rows():
    base = {
        "h2h_draw_rate": 0.4,
        "abs_hcap": 0.5,
        "had_d": 3.3,
        "h2h_one_goal_margin_rate": 0.5,
        "recent_low_scoring_sum": 1.2,
        "recent_draw_sum": 0.6,
    }
    rules = {rule.name: rule for rule in draw_rules()}

    assert rules["DRAW_V31_A"].fn(base) is True
    assert rules["DRAW_V31_B"].fn(base) is True
    assert rules["DRAW_V31_C"].fn(base) is True
    assert rules["DRAW_V31_D"].fn(base) is True
    assert rules["DRAW_V31_A"].fn({**base, "abs_hcap": 1.0}) is False
    assert rules["DRAW_V31_C"].fn({**base, "had_d": 3.8}) is False


def test_hdraw_v31_rules_match_expected_rows():
    base = {
        "abs_hcap": 1.0,
        "rank_gap": 10,
        "hhad_d": 3.6,
        "venue_draw_sum": 0.5,
        "season_draw_sum": 0.45,
        "home_recent_win_by_1_rate": 0.2,
        "away_recent_loss_by_1_rate": 0.2,
        "away_recent_ga_per_match": 1.4,
        "away_recent_loss_by_2plus_rate": 0.2,
    }
    rules = {rule.name: rule for rule in hdraw_rules()}

    assert rules["HDRAW_V31_A0"].fn(base) is True
    assert rules["HDRAW_V31_A1"].fn(base) is True
    assert rules["HDRAW_V31_A2"].fn(base) is True
    assert rules["HDRAW_V31_B"].fn(base) is True
    assert rules["HDRAW_V31_C"].fn({**base, "rank_gap": 17}) is True
    assert rules["HDRAW_V31_A0"].fn({**base, "rank_gap": 3}) is False
    assert rules["HDRAW_V31_A1"].fn({**base, "home_recent_win_by_1_rate": 0.0}) is False


def test_evaluate_rules_emits_candidate_rows():
    rows = [
        {
            "match_id": 1,
            "match_date": date(2026, 1, 1),
            "is_draw": True,
            "is_hdraw": False,
            "had_d": 3.3,
            "hhad_d": 3.6,
            "h2h_draw_rate": 0.4,
            "abs_hcap": 0.5,
            "h2h_one_goal_margin_rate": 0.5,
            "recent_low_scoring_sum": 1.2,
            "recent_draw_sum": 0.6,
        }
    ]

    out = evaluate_rules(rows, draw_rules())

    assert {row["rule_name"] for row in out} == {
        "DRAW_V31_A",
        "DRAW_V31_B",
        "DRAW_V31_C",
        "DRAW_V31_D",
    }
    assert all(row["channel"] == "draw" for row in out)
    assert all(row["odds"] == 3.3 for row in out)
    assert all(row["hit"] is True for row in out)


def test_portfolio_rows_keeps_highest_priority_per_match_and_prefers_hdraw():
    candidates = [
        {"match_id": 1, "match_date": date(2026, 1, 1), "channel": "draw", "rule_priority": 100, "rule_name": "DRAW_V31_D"},
        {"match_id": 1, "match_date": date(2026, 1, 1), "channel": "hdraw", "rule_priority": 90, "rule_name": "HDRAW_V31_A0"},
        {"match_id": 2, "match_date": date(2026, 1, 2), "channel": "draw", "rule_priority": 70, "rule_name": "DRAW_V31_C"},
    ]

    out = portfolio_rows(candidates)

    assert [row["rule_name"] for row in out] == ["HDRAW_V31_A0", "DRAW_V31_C"]


def test_window_ranges_uses_non_overlapping_90_day_windows():
    assert window_ranges(date(2026, 1, 1), date(2026, 4, 10), days=90) == [
        (date(2026, 1, 1), date(2026, 3, 31)),
        (date(2026, 4, 1), date(2026, 4, 10)),
    ]


def test_score_values_for_rule_maps_priority_to_display_score():
    assert score_values_for_rule("HDRAW_V31_A1") == (116, Decimal("0.0150"))
    assert score_values_for_rule("HDRAW_V31_A0") == (112, Decimal("0.0120"))
    assert score_values_for_rule("HDRAW_V31_B") == (108, Decimal("0.0100"))
    assert score_values_for_rule("HDRAW_V31_C") == (104, Decimal("0.0080"))
    assert score_values_for_rule("DRAW_V31_D") == (106, Decimal("0.0080"))
    assert score_values_for_rule("DRAW_V31_A") == (102, Decimal("0.0060"))


def test_v32_draw_rule_requires_positive_v31_rule_and_price_floor():
    base = {
        "h2h_draw_rate": 0.2,
        "h2h_one_goal_margin_rate": 0.5,
        "recent_low_scoring_sum": 1.2,
        "recent_draw_sum": 0.0,
        "abs_hcap": 0.5,
        "had_d": 3.2,
    }
    rule = v32_draw_rules()[0]

    assert rule.name == "DRAW_V32_CORE"
    assert rule.fn(base) is True
    assert rule.fn({**base, "had_d": 3.05}) is False
    assert rule.fn(
        {
            **base,
            "h2h_one_goal_margin_rate": 0.1,
            "recent_draw_sum": 0.6,
            "had_d": 3.2,
        }
    ) is False


def test_v32_hdraw_rule_keeps_only_hdraw_a_family():
    base = {
        "abs_hcap": 1.0,
        "rank_gap": 10,
        "hhad_d": 3.6,
        "venue_draw_sum": 0.5,
        "season_draw_sum": 0.45,
        "home_recent_win_by_1_rate": 0.0,
        "away_recent_loss_by_1_rate": 0.0,
        "away_recent_ga_per_match": 2.2,
        "away_recent_loss_by_2plus_rate": 0.7,
    }
    rule = v32_hdraw_rules()[0]

    assert rule.name == "HDRAW_V32_CORE"
    assert rule.fn(base) is True
    assert rule.fn({**base, "rank_gap": 17}) is False


def test_v32_version_uses_filtered_candidate_model_and_scores():
    version = candidate_version("v32")

    assert version.model_name == V32_CANDIDATE_MODEL_NAME
    assert [rule.name for rule in version.rules] == ["DRAW_V32_CORE", "HDRAW_V32_CORE"]
    assert score_values_for_rule("HDRAW_V32_CORE") == (116, Decimal("0.0150"))
    assert score_values_for_rule("DRAW_V32_CORE") == (108, Decimal("0.0100"))


def test_csv_lines_contains_required_columns():
    rows = [
        {
            "match_id": 1,
            "match_date": date(2026, 1, 1),
            "league": "测试联赛",
            "home_team": "主队",
            "away_team": "客队",
            "rule_name": "DRAW_V31_A",
            "channel": "draw",
            "bet_type": "draw",
            "odds": 3.3,
            "hit": True,
            "pnl": 230.0,
            "abs_hcap": 0.5,
            "rank_gap": 4,
            "had_d": 3.3,
            "hhad_d": 3.6,
            "home_recent_win_by_1_rate": 0.2,
            "away_recent_loss_by_1_rate": 0.2,
            "away_recent_ga_per_match": 1.4,
            "h2h_draw_rate": 0.4,
            "h2h_one_goal_margin_rate": 0.5,
            "recent_low_scoring_sum": 1.2,
        }
    ]

    text = "\n".join(csv_lines(rows))

    assert "match_id,match_date,league,home_team,away_team" in text
    assert "DRAW_V31_A" in text


def test_render_report_contains_required_sections():
    report = render_report(
        rows=[],
        candidates=[],
        portfolio=[],
        start=date(2024, 9, 28),
        end=date(2026, 4, 22),
        detail_path="docs/analysis/v32-filtered-candidates.csv",
        write_summary={
            "model_config_id": 9,
            "scored_matches": 0,
            "recommended_scores": 0,
            "draw_scores": 0,
            "handicap_draw_scores": 0,
            "replaced_old_scores": 0,
        },
    )

    assert "# V3.2 过滤器候选模型回测报告" in report
    assert "## 1. 数据范围" in report
    assert "## 4. 候选规则独立表现" in report
    assert "## 7. 结论" in report
    assert "model_config_id" in report

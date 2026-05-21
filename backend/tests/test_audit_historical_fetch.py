from __future__ import annotations

from decimal import Decimal

from app.scripts.audit_historical_fetch import compare_fields, normalize_compare_value


def test_normalize_compare_value_treats_decimal_and_string_as_equal():
    assert normalize_compare_value(Decimal("2.300")) == normalize_compare_value("2.3")


def test_compare_fields_reports_missing_existing():
    diffs = compare_fields(
        match_id=202602286002,
        section="odds",
        existing={"draw_odds": None},
        audit={"draw_odds": Decimal("3.10")},
        fields=["draw_odds"],
    )

    assert diffs == [
        {
            "match_id": 202602286002,
            "section": "odds",
            "field_name": "draw_odds",
            "existing_value": None,
            "audit_value": "3.1",
            "severity": "missing_existing",
        }
    ]


def test_compare_fields_reports_mismatch():
    diffs = compare_fields(
        match_id=202602286002,
        section="result",
        existing={"home_score": 1},
        audit={"home_score": 2},
        fields=["home_score"],
    )

    assert diffs == [
        {
            "match_id": 202602286002,
            "section": "result",
            "field_name": "home_score",
            "existing_value": "1",
            "audit_value": "2",
            "severity": "mismatch",
        }
    ]


def test_compare_fields_ignores_equivalent_values():
    diffs = compare_fields(
        match_id=202602286002,
        section="match",
        existing={"home_team": "浦和红钻", "had_d": Decimal("3.100")},
        audit={"home_team": "浦和红钻", "had_d": "3.1"},
        fields=["home_team", "had_d"],
    )

    assert diffs == []

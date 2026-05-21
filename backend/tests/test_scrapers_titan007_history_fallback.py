from __future__ import annotations

from decimal import Decimal

from app.scrapers.titan007.history import (
    TITAN_HKJC_COMPANY_ID,
    TitanOdds,
    merge_titan_odds_by_priority,
    parse_oddslist_js_company,
)


def _odds(match_id: str, win: str) -> TitanOdds:
    return TitanOdds(
        match_id=match_id,
        win_odds=Decimal(win),
        draw_odds=Decimal("3.10"),
        lose_odds=Decimal("2.80"),
        handicap_value=Decimal("0"),
        win_handicap_odds=Decimal("0.90"),
        draw_handicap_odds=None,
        lose_handicap_odds=Decimal("0.92"),
    )


def test_merge_titan_odds_keeps_primary_when_both_bookmakers_have_match():
    merged = merge_titan_odds_by_priority([
        [ _odds("2915931", "2.10") ],
        [ _odds("2915931", "2.25") ],
    ])

    assert len(merged) == 1
    assert merged[0].match_id == "2915931"
    assert merged[0].win_odds == Decimal("2.10")


def test_merge_titan_odds_uses_fallback_for_missing_primary_match():
    merged = merge_titan_odds_by_priority([
        [ _odds("primary-only", "1.80") ],
        [ _odds("fallback-only", "2.35") ],
    ])

    assert [item.match_id for item in merged] == ["primary-only", "fallback-only"]
    assert merged[1].win_odds == Decimal("2.35")


def test_merge_titan_odds_fills_missing_primary_euro_odds_from_fallback():
    primary = TitanOdds(
        match_id="2915931",
        win_odds=None,
        draw_odds=None,
        lose_odds=None,
        handicap_value=Decimal("0.25"),
        win_handicap_odds=Decimal("0.90"),
        draw_handicap_odds=None,
        lose_handicap_odds=Decimal("0.92"),
    )
    fallback = TitanOdds(
        match_id="2915931",
        win_odds=Decimal("1.70"),
        draw_odds=Decimal("3.70"),
        lose_odds=Decimal("3.65"),
        handicap_value=None,
        win_handicap_odds=None,
        draw_handicap_odds=None,
        lose_handicap_odds=None,
    )

    merged = merge_titan_odds_by_priority([[primary], [fallback]])

    assert len(merged) == 1
    assert merged[0].win_odds == Decimal("1.70")
    assert merged[0].draw_odds == Decimal("3.70")
    assert merged[0].lose_odds == Decimal("3.65")
    assert merged[0].handicap_value == Decimal("0.25")
    assert merged[0].win_handicap_odds == Decimal("0.90")
    assert merged[0].lose_handicap_odds == Decimal("0.92")


def test_parse_oddslist_js_company_extracts_hkjc_current_euro_odds():
    js = (
        'var game=Array('
        '"999|150744088|Other Bookmaker|1.66|3.7|4.5|55.02|24.68|20.3|91.33|'
        '1.85|3.8|3.75|50.5|24.59|24.91|93.43|0.92|0.95|0.95|'
        '2026,03-1,01,07,00,00|其他公司|1|0|0.82|0.93|1.14",'
        '"432|150837591|HK Jockey Club|1.7|3.75|3.6|51.93|23.54|24.52|88.29|'
        '1.7|3.7|3.65|51.94|23.87|24.19|88.3|0.84|0.93|0.92|'
        '2026,03-1,01,07,00,00|香港马*(中国香港)|1|0|0.84|0.94|0.91"'
        ');'
    )

    odds = parse_oddslist_js_company("2915931", js, TITAN_HKJC_COMPANY_ID)

    assert odds is not None
    assert odds.match_id == "2915931"
    assert odds.win_odds == Decimal("1.7")
    assert odds.draw_odds == Decimal("3.7")
    assert odds.lose_odds == Decimal("3.65")
    assert odds.handicap_value is None
    assert odds.win_handicap_odds is None
    assert odds.draw_handicap_odds is None
    assert odds.lose_handicap_odds is None


def test_parse_oddslist_js_company_returns_none_when_company_missing():
    js = (
        'var game=Array('
        '"999|150744088|Other Bookmaker|1.66|3.7|4.5|55.02|24.68|20.3|91.33|'
        '1.85|3.8|3.75|50.5|24.59|24.91|93.43|0.92|0.95|0.95|'
        '2026,03-1,01,07,00,00|其他公司|1|0|0.82|0.93|1.14"'
        ');'
    )

    odds = parse_oddslist_js_company("2915931", js, TITAN_HKJC_COMPANY_ID)

    assert odds is None

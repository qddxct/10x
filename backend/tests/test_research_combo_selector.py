from datetime import date, timedelta

from app.research.combo_selector import score_pair, select_combo_tickets
from app.research.types import ResearchCandidate


def _candidate(
    match_id: int,
    day: date,
    *,
    league="英超",
    bet_type="draw",
    odds=3.3,
    hit=True,
    score=108,
):
    return ResearchCandidate(
        match_id=match_id,
        match_date=day,
        league=league,
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


def test_score_pair_rejects_outside_combo_odds_range():
    day = date(2026, 4, 1)
    low = score_pair(_candidate(1, day, odds=2.8), _candidate(2, day, odds=2.9), profile="balanced")
    high = score_pair(
        _candidate(1, day, odds=4.0), _candidate(2, day, odds=4.0), profile="balanced"
    )
    assert low is None
    assert high is None


def test_score_pair_rewards_mixed_type_and_different_league():
    day = date(2026, 4, 1)
    mixed = score_pair(
        _candidate(1, day, league="英超", bet_type="draw"),
        _candidate(2, day, league="德甲", bet_type="handicap_draw", score=116),
        profile="balanced",
    )
    same_type_same_league = score_pair(
        _candidate(3, day, league="英超", bet_type="draw"),
        _candidate(4, day, league="英超", bet_type="draw"),
        profile="balanced",
    )
    assert mixed is not None
    assert same_type_same_league is not None
    assert mixed > same_type_same_league


def test_balanced_selector_prefers_best_pair_per_day():
    day = date(2026, 4, 1)
    tickets = select_combo_tickets(
        [
            _candidate(1, day, league="英超", bet_type="draw", odds=3.3, hit=True),
            _candidate(
                2, day, league="德甲", bet_type="handicap_draw", odds=3.4, hit=True, score=116
            ),
            _candidate(3, day, league="英超", bet_type="draw", odds=3.8, hit=False),
        ],
        strategy="balanced_selector",
    )
    assert len(tickets) == 1
    assert {leg.match_id for leg in tickets[0].legs} == {1, 2}
    assert tickets[0].is_hit is True


def test_frequency_selector_pairs_across_two_days():
    day = date(2026, 4, 1)
    tickets = select_combo_tickets(
        [_candidate(1, day), _candidate(2, day + timedelta(days=1), league="德甲")],
        strategy="frequency_selector",
    )
    assert len(tickets) == 1
    assert tickets[0].ticket_date == day


def test_v34_ticket_payload_keeps_auditable_leg_details():
    from app.research.combo_selector import _ticket
    from app.scripts.v34_combo_selector import _random_ticket_payload, _ticket_payload

    day = date(2026, 4, 1)
    ticket = _ticket(
        "frequency_selector",
        day,
        _candidate(11, day, league="英冠", bet_type="draw", odds=3.2, hit=True),
        _candidate(
            12,
            day + timedelta(days=1),
            league="西甲",
            bet_type="handicap_draw",
            odds=3.5,
            hit=False,
        ),
    )

    payload = _ticket_payload("frequency_selector", ticket)

    assert payload["strategy"] == "frequency_selector"
    assert payload["ticket_date"] == "2026-04-01"
    assert payload["combo_odds"] == 11.2
    assert payload["stake"] == 100.0
    assert payload["is_hit"] is False
    assert payload["pnl"] == -100.0
    assert payload["legs"][0]["bet_label"] == "平"
    assert payload["legs"][1]["bet_label"] == "让平 (+1)"
    assert payload["legs"][1]["handicap_value"] == 1.0
    assert payload["legs"][1]["result_label"] == "未命中"

    random_payload = _random_ticket_payload(
        "frequency_selector", "全市场随机", ticket
    )
    assert random_payload["strategy"] == "frequency_selector"
    assert random_payload["group_type"] == "random_control"
    assert random_payload["control_label"] == "全市场随机"
    assert random_payload["legs"][0]["bet_label"] == "平"


def test_v34_amount_summary_uses_fixed_stake_and_net_pnl():
    from app.scripts.v34_combo_selector import _best_strategy_amount_summary

    summary = _best_strategy_amount_summary(
        {"strategy": "frequency_selector", "combo_count": 3, "pnl": 125.5}
    )

    assert summary == {
        "best_strategy_stake": 300.0,
        "best_strategy_pnl": 125.5,
        "best_strategy_return": 425.5,
    }

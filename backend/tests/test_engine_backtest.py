from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from app.engine.backtest import (
    BetOutcome,
    aggregate,
    decide_outcome,
    simulate_bet,
)


def test_decide_outcome_draw_hit():
    assert decide_outcome("draw", asian_handicap="0", result="draw") is True


def test_decide_outcome_draw_miss():
    assert decide_outcome("draw", asian_handicap="0", result="home_win") is False


def test_decide_outcome_handicap_draw_hit():
    assert (
        decide_outcome(
            "handicap_draw",
            asian_handicap="-0.25",
            result="home_win",
            handicap_result="draw",
        )
        is True
    )


def test_decide_outcome_handicap_draw_miss():
    assert (
        decide_outcome(
            "handicap_draw",
            asian_handicap="-0.25",
            result="home_win",
            handicap_result="home_win",
        )
        is False
    )


def test_decide_outcome_unknown_bet_type():
    assert decide_outcome("unknown", "0", "draw") is False


def test_simulate_bet_hit():
    pnl_fixed, pnl_kelly, stake_kelly = simulate_bet(
        odds=Decimal("3.20"),
        kelly_pct=Decimal("0.02"),
        current_capital=Decimal("10000"),
        is_hit=True,
    )
    assert pnl_fixed == Decimal("2.20")
    assert stake_kelly == Decimal("200.00")
    assert pnl_kelly == Decimal("440.00")


def test_simulate_bet_miss():
    pnl_fixed, pnl_kelly, stake_kelly = simulate_bet(
        odds=Decimal("3.20"),
        kelly_pct=Decimal("0.02"),
        current_capital=Decimal("10000"),
        is_hit=False,
    )
    assert pnl_fixed == Decimal("-1")
    assert stake_kelly == Decimal("200.00")
    assert pnl_kelly == Decimal("-200.00")


def test_simulate_bet_zero_capital_halts_kelly():
    pnl_fixed, pnl_kelly, stake_kelly = simulate_bet(
        odds=Decimal("3.00"),
        kelly_pct=Decimal("0.02"),
        current_capital=Decimal("0"),
        is_hit=True,
    )
    assert pnl_fixed == Decimal("2.00")
    assert stake_kelly == Decimal("0")
    assert pnl_kelly == Decimal("0")


def test_simulate_bet_negative_capital_halts_kelly():
    pnl_fixed, pnl_kelly, stake_kelly = simulate_bet(
        odds=Decimal("3.00"),
        kelly_pct=Decimal("0.02"),
        current_capital=Decimal("-500"),
        is_hit=False,
    )
    assert pnl_fixed == Decimal("-1")
    assert stake_kelly == Decimal("0")
    assert pnl_kelly == Decimal("0")


def test_simulate_bet_zero_kelly():
    pnl_fixed, pnl_kelly, stake_kelly = simulate_bet(
        odds=Decimal("3.00"),
        kelly_pct=Decimal("0"),
        current_capital=Decimal("10000"),
        is_hit=True,
    )
    assert pnl_fixed == Decimal("2.00")
    assert stake_kelly == Decimal("0")
    assert pnl_kelly == Decimal("0")


def _outcome(
    *,
    match_date: date,
    odds: str,
    kelly_pct: str,
    is_hit: bool,
    score: int = 90,
    league: str = "英超",
    pnl_fixed: str,
    pnl_kelly: str,
    stake_kelly: str,
) -> BetOutcome:
    return BetOutcome(
        score_id=1,
        match_id=1,
        match_date=match_date,
        league=league,
        total_score=score,
        bet_type="draw",
        odds=Decimal(odds),
        kelly_pct=Decimal(kelly_pct),
        stake_fixed=Decimal("1"),
        stake_kelly=Decimal(stake_kelly),
        pnl_fixed=Decimal(pnl_fixed),
        pnl_kelly=Decimal(pnl_kelly),
        is_hit=is_hit,
    )


def test_aggregate_empty():
    stats = aggregate([], initial_capital=Decimal("10000"))
    assert stats.total_bets == 0
    assert stats.hit_count == 0
    assert stats.hit_rate == Decimal("0")
    assert stats.roi_fixed == Decimal("0")
    assert stats.roi_kelly == Decimal("0")
    assert stats.profit_loss_fixed == Decimal("0")
    assert stats.profit_loss_kelly == Decimal("0")
    assert stats.by_score_band == {}
    assert stats.by_league == {}
    assert stats.equity_curve == []


def test_aggregate_mixed_results():
    outs = [
        _outcome(
            match_date=date(2026, 4, 1),
            odds="3.20",
            kelly_pct="0.02",
            is_hit=True,
            score=90,
            league="英超",
            pnl_fixed="2.20",
            pnl_kelly="440.00",
            stake_kelly="200.00",
        ),
        _outcome(
            match_date=date(2026, 4, 2),
            odds="3.00",
            kelly_pct="0.02",
            is_hit=False,
            score=80,
            league="西甲",
            pnl_fixed="-1",
            pnl_kelly="-200.00",
            stake_kelly="200.00",
        ),
    ]
    stats = aggregate(outs, initial_capital=Decimal("10000"))
    assert stats.total_bets == 2
    assert stats.hit_count == 1
    assert stats.hit_rate == pytest.approx(Decimal("0.5"))
    assert stats.profit_loss_fixed == Decimal("1.20")
    assert stats.profit_loss_kelly == Decimal("240.00")
    assert stats.roi_fixed == pytest.approx(Decimal("0.6"))
    assert stats.roi_kelly == pytest.approx(Decimal("0.024"))
    assert "84-100" in stats.by_score_band
    assert stats.by_score_band["84-100"]["bets"] == 1
    assert stats.by_score_band["84-100"]["hits"] == 1
    assert stats.by_league["英超"]["bets"] == 1
    assert stats.by_league["西甲"]["hits"] == 0
    assert len(stats.equity_curve) == 2
    assert stats.equity_curve[0]["cumulative_pnl_fixed"] == Decimal("2.20")
    assert stats.equity_curve[1]["cumulative_pnl_fixed"] == Decimal("1.20")
    assert stats.equity_curve[1]["cumulative_pnl_kelly"] == Decimal("240.00")


def test_aggregate_equity_curve_groups_same_day():
    outs = [
        _outcome(
            match_date=date(2026, 4, 1),
            odds="3.0",
            kelly_pct="0.02",
            is_hit=True,
            pnl_fixed="2",
            pnl_kelly="400",
            stake_kelly="200",
        ),
        _outcome(
            match_date=date(2026, 4, 1),
            odds="3.0",
            kelly_pct="0.02",
            is_hit=False,
            pnl_fixed="-1",
            pnl_kelly="-200",
            stake_kelly="200",
        ),
    ]
    stats = aggregate(outs, initial_capital=Decimal("10000"))
    assert len(stats.equity_curve) == 1
    assert stats.equity_curve[0]["cumulative_pnl_fixed"] == Decimal("1")
    assert stats.equity_curve[0]["cumulative_pnl_kelly"] == Decimal("200")

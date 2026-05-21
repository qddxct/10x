from datetime import date, datetime, time
from decimal import Decimal

import pytest
from app.engine.backtest import simulate_bet
from app.engine.backtest_service import BacktestService
from app.models import (
    League,
    ModelConfig,
    SportteryMatch,
    SportteryMatchOdds,
    SportteryMatchResult,
    SportteryMatchTeamStats,
)
from app.scripts.seed import DEFAULT_KELLY_BANDS, DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS
from sqlalchemy.orm import Session


def test_simulate_bet_fixed_stake_hit():
    pnl_fixed, pnl_kelly, stake_kelly = simulate_bet(
        odds=Decimal("3.10"),
        kelly_pct=Decimal("0"),
        current_capital=Decimal("0"),
        is_hit=True,
        stake_fixed=Decimal("100"),
    )
    assert pnl_fixed == Decimal("210.00")
    assert pnl_kelly == Decimal("0.00")
    assert stake_kelly == Decimal("0.00")


def test_simulate_bet_fixed_stake_miss():
    pnl_fixed, _, _ = simulate_bet(
        odds=Decimal("3.10"),
        kelly_pct=Decimal("0"),
        current_capital=Decimal("0"),
        is_hit=False,
        stake_fixed=Decimal("100"),
    )
    assert pnl_fixed == Decimal("-100.00")


def test_simulate_bet_fixed_stake_default_unit():
    """Backwards-compatible: stake_fixed defaults to 1."""
    pnl_fixed, _, _ = simulate_bet(
        odds=Decimal("3.10"),
        kelly_pct=Decimal("0"),
        current_capital=Decimal("0"),
        is_hit=True,
    )
    assert pnl_fixed == Decimal("2.10")


@pytest.fixture
def config(db: Session) -> ModelConfig:
    cfg = ModelConfig(
        name="default",
        weights_json=dict(DEFAULT_WEIGHTS),
        thresholds_json=dict(DEFAULT_THRESHOLDS),
        kelly_bands_json=dict(DEFAULT_KELLY_BANDS),
    )
    db.add(cfg)
    db.flush()
    return cfg


@pytest.fixture
def league(db: Session) -> League:
    lg = League(name="英超")
    db.add(lg)
    db.flush()
    return lg


def _make_draw_match(db: Session, league: League, match_date: date) -> SportteryMatch:
    m = SportteryMatch(
        id=int(match_date.strftime("%Y%m%d") + "6001"),
        league_id=league.id,
        home_team="H",
        away_team="A",
        match_date=datetime.combine(match_date, time(20, 0)),
        status="finished",
        had_d=Decimal("2.95"),
    )
    db.add(m)
    db.flush()

    db.add(
        SportteryMatchOdds(
            match_id=m.id,
            source="sporttery",
            win_odds=Decimal("2.50"),
            draw_odds=Decimal("3.10"),
            lose_odds=Decimal("2.60"),
            handicap_value=Decimal("0.0"),
            draw_handicap_odds=Decimal("3.60"),
            asian_handicap="0.00",
            total_goals=Decimal("2.25"),
            scraped_at=datetime(2026, 4, 1, 12, 0),
        )
    )
    db.add(
        SportteryMatchTeamStats(
            match_id=m.id,
            home_rank=5,
            away_rank=6,
            home_season_wins=10,
            home_season_draws=8,
            home_season_losses=6,
            away_season_wins=9,
            away_season_draws=9,
            away_season_losses=7,
            home_recent_form="WDDLW",
            away_recent_form="DDWLL",
            scraped_at=datetime(2026, 4, 1, 12, 0),
        )
    )
    db.add(
        SportteryMatchResult(
            match_id=m.id,
            home_score=1,
            away_score=1,
            result="draw",
            handicap_result="draw",
        )
    )
    return m


def test_backtest_run_uses_fixed_stake(db: Session, config: ModelConfig, league: League):
    _make_draw_match(db, league, date(2026, 4, 1))
    db.commit()

    svc = BacktestService(db)
    session = svc.run(
        model_config_id=config.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 2),
        fixed_stake=Decimal("50"),
    )
    assert session.fixed_stake == Decimal("50.00")
    if session.total_bets > 0:
        assert session.profit_loss == Decimal("50") * (Decimal("2.95") - Decimal("1"))


def test_backtest_run_populates_bets_detail(
    db: Session, config: ModelConfig, league: League
):
    _make_draw_match(db, league, date(2026, 4, 1))
    db.commit()

    svc = BacktestService(db)
    session = svc.run(
        model_config_id=config.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 2),
        fixed_stake=Decimal("100"),
    )
    assert session.bets_detail is not None
    assert isinstance(session.bets_detail, list)
    assert len(session.bets_detail) == session.total_bets
    if session.total_bets > 0:
        row = session.bets_detail[0]
        assert row["match_id"]
        assert row["match_date"] == "2026-04-01"
        assert row["league"] == "英超"
        assert row["bet_type"] in ("draw", "handicap_draw")
        assert "handicap_value" in row
        assert row["stake_fixed"] == "100.00"
        assert row["is_hit"] is True
        assert row["home_score"] == 1
        assert row["away_score"] == 1
        assert row["odds"] == "2.95"
        assert row["pnl_fixed"] == "195.00"

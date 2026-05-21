from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

import pytest
from app.engine.backtest_service import BacktestService
from app.models import (
    BacktestSession,
    League,
    ModelConfig,
    SportteryMatch,
    SportteryMatchOdds,
    SportteryMatchResult,
    SportteryMatchScore,
    SportteryMatchTeamStats,
)
from app.scripts.seed import DEFAULT_KELLY_BANDS, DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS
from sqlalchemy.orm import Session


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


def _make_match_with_result(
    db: Session,
    league: League,
    *,
    match_date: date,
    result: str,
    handicap_result: str | None = None,
    draw_odds: Decimal = Decimal("3.10"),
    asian_handicap: str = "平手",
) -> SportteryMatch:
    seq = int(match_date.strftime("%d"))
    m = SportteryMatch(
        id=int(match_date.strftime("%Y%m%d") + "6" + f"{seq:03d}"),
        league_id=league.id,
        home_team="H",
        away_team="A",
        match_date=datetime.combine(match_date, time(20, 0)),
        status="finished",
    )
    db.add(m)
    db.flush()

    odds = SportteryMatchOdds(
        match_id=m.id,
        source="sporttery",
        win_odds=Decimal("2.50"),
        draw_odds=draw_odds,
        lose_odds=Decimal("2.60"),
        handicap_value=Decimal("0.0"),
        draw_handicap_odds=Decimal("3.60"),
        asian_handicap=asian_handicap,
        total_goals=Decimal("2.25"),
        scraped_at=datetime.utcnow(),
    )
    db.add(odds)

    stats = SportteryMatchTeamStats(
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
        scraped_at=datetime.utcnow(),
    )
    db.add(stats)

    res = SportteryMatchResult(
        match_id=m.id,
        home_score=1 if result == "home_win" else (0 if result == "draw" else 0),
        away_score=0 if result == "home_win" else (0 if result == "draw" else 1),
        result=result,
        handicap_result=handicap_result,
    )
    db.add(res)
    db.flush()
    return m


def test_backtest_service_runs_and_persists_session(
    db: Session, config: ModelConfig, league: League
):
    _make_match_with_result(
        db,
        league,
        match_date=date(2026, 4, 1),
        result="draw",
        handicap_result="draw",
    )
    _make_match_with_result(
        db,
        league,
        match_date=date(2026, 4, 2),
        result="home_win",
        handicap_result="home_win",
    )
    db.commit()

    svc = BacktestService(db)
    session = svc.run(
        model_config_id=config.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 30),
        mode="both",
        initial_capital=Decimal("10000"),
    )

    assert session.id is not None
    assert session.model_config_id == config.id
    assert session.date_from == date(2026, 4, 1)
    assert session.date_to == date(2026, 4, 30)
    assert session.total_bets >= 1
    assert session.mode == "both"
    assert session.initial_capital == Decimal("10000.00")
    assert session.equity_curve is not None
    assert isinstance(session.equity_curve, list)


def test_backtest_service_skips_matches_without_results(
    db: Session, config: ModelConfig, league: League
):
    m = SportteryMatch(
        id=202604016001,
        league_id=league.id,
        home_team="H",
        away_team="A",
        match_date=datetime.combine(date(2026, 4, 1), time(20, 0)),
        status="scheduled",
    )
    db.add(m)
    db.flush()
    odds = SportteryMatchOdds(
        match_id=m.id,
        source="sporttery",
        win_odds=Decimal("2.50"),
        draw_odds=Decimal("3.10"),
        lose_odds=Decimal("2.60"),
        asian_handicap="平手",
        total_goals=Decimal("2.25"),
        scraped_at=datetime.utcnow(),
    )
    db.add(odds)
    db.commit()

    svc = BacktestService(db)
    session = svc.run(
        model_config_id=config.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 30),
        mode="both",
        initial_capital=Decimal("10000"),
    )

    assert session.total_bets == 0
    assert session.hit_count == 0


def test_backtest_service_counts_hits_and_misses(
    db: Session, config: ModelConfig, league: League
):
    _make_match_with_result(
        db,
        league,
        match_date=date(2026, 4, 1),
        result="draw",
        handicap_result="draw",
    )
    _make_match_with_result(
        db,
        league,
        match_date=date(2026, 4, 2),
        result="home_win",
        handicap_result="home_win",
    )
    _make_match_with_result(
        db,
        league,
        match_date=date(2026, 4, 3),
        result="draw",
        handicap_result="draw",
    )
    db.commit()

    svc = BacktestService(db)
    session = svc.run(
        model_config_id=config.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 30),
        mode="both",
        initial_capital=Decimal("10000"),
    )
    if session.total_bets > 0:
        assert 0 <= session.hit_count <= session.total_bets
        assert session.total_bets == db.query(BacktestSession).one().total_bets


def test_backtest_service_does_not_persist_match_scores(
    db: Session, config: ModelConfig, league: League
):
    _make_match_with_result(
        db,
        league,
        match_date=date(2026, 4, 1),
        result="draw",
        handicap_result="draw",
    )
    db.commit()
    assert db.query(SportteryMatchScore).count() == 0

    svc = BacktestService(db)
    svc.run(
        model_config_id=config.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 30),
        mode="both",
        initial_capital=Decimal("10000"),
    )

    assert db.query(SportteryMatchScore).count() == 0


def test_backtest_service_reuses_existing_match_score(
    db: Session, config: ModelConfig, league: League
):
    m = _make_match_with_result(
        db,
        league,
        match_date=date(2026, 4, 1),
        result="draw",
        handicap_result="draw",
    )
    db.add(
        SportteryMatchScore(
            match_id=m.id,
            model_config_id=config.id,
            user_id=None,
            euro_score=20,
            asian_score=20,
            goals_score=20,
            intent_score=15,
            compression_score=20,
            team_stats_score=20,
            total_score=115,
            bet_type="draw",
            kelly_pct=Decimal("0.05"),
            is_recommended=True,
        )
    )
    db.commit()

    svc = BacktestService(db)
    session = svc.run(
        model_config_id=config.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 30),
        mode="both",
        initial_capital=Decimal("10000"),
    )

    assert session.total_bets == 1
    assert db.query(SportteryMatchScore).count() == 1
    score = db.query(SportteryMatchScore).one()
    assert score.total_score == 115

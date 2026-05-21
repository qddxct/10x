from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from app.models import (
    BacktestSession,
    Base,
    League,
    Match,
    MatchOdds,
    MatchResult,
    MatchScore,
    MatchTeamStats,
    ModelConfig,
    ScrapeLog,
    User,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_metadata_contains_all_tables():
    expected = {
        "users",
        "leagues",
        "matches",
        "match_odds",
        "match_results",
        "match_team_stats",
        "match_scores",
        "model_configs",
        "backtest_sessions",
        "scrape_logs",
    }
    assert expected.issubset(set(Base.metadata.tables.keys()))


def test_create_full_match_graph(db: Session):
    league = League(name="Premier League", country="England", draw_rate_tier="medium")
    db.add(league)
    db.flush()

    match = Match(
        league_id=league.id,
        sporttery_match_id="E001",
        home_team="Arsenal",
        away_team="Chelsea",
        match_date=datetime(2026, 5, 1, 22, 0, 0),
        status="scheduled",
    )
    db.add(match)
    db.flush()

    odds = MatchOdds(
        match_id=match.id,
        source="sporttery",
        win_odds=Decimal("2.10"),
        draw_odds=Decimal("3.40"),
        lose_odds=Decimal("3.30"),
        scraped_at=datetime(2026, 4, 21, 8, 30, 0),
    )
    db.add(odds)

    result = MatchResult(match_id=match.id, home_score=1, away_score=1, result="draw")
    db.add(result)

    cfg = ModelConfig(
        name="default",
        weights_json={"euro": 1.0},
        thresholds_json={"min": 6},
        kelly_bands_json={"low": {"kelly_pct": 0.005}},
    )
    db.add(cfg)
    db.flush()

    score = MatchScore(
        match_id=match.id,
        model_config_id=cfg.id,
        euro_score=2,
        asian_score=2,
        goals_score=1,
        intent_score=1,
        compression_score=1,
        team_stats_score=1,
        total_score=8,
        bet_type="draw",
        kelly_pct=Decimal("0.01"),
        is_recommended=True,
    )
    db.add(score)

    stats = MatchTeamStats(
        match_id=match.id,
        home_rank=4,
        away_rank=10,
        scraped_at=datetime(2026, 4, 21, 8, 30, 0),
    )
    db.add(stats)

    backtest = BacktestSession(
        model_config_id=cfg.id,
        date_from=date(2026, 1, 1),
        date_to=date(2026, 4, 30),
        total_bets=100,
        hit_count=42,
        hit_rate=Decimal("0.4200"),
        roi=Decimal("0.1200"),
        profit_loss=Decimal("1500.00"),
    )
    db.add(backtest)

    log = ScrapeLog(
        source="sporttery",
        job_name="daily_odds",
        status="success",
        started_at=datetime(2026, 4, 21, 8, 30, 0),
        finished_at=datetime(2026, 4, 21, 8, 31, 0),
        records_count=10,
    )
    db.add(log)

    user = User(phone="13800138000", name="tester", password_hash="hashed")
    db.add(user)

    db.commit()

    assert db.query(Match).count() == 1
    assert db.query(MatchScore).first().total_score == 8
    assert db.query(ModelConfig).first().weights_json == {"euro": 1.0}


def test_scrape_log_running_status_roundtrip(db: Session):
    log = ScrapeLog(
        source="sporttery",
        job_name="daily_odds",
        status="running",
        started_at=datetime(2026, 4, 21, 8, 30, 0),
        records_count=0,
    )
    db.add(log)
    db.commit()

    fetched = db.query(ScrapeLog).one()
    assert fetched.status == "running"
    assert fetched.finished_at is None


def test_match_scores_unique_per_match_and_config(db: Session):
    from sqlalchemy.exc import IntegrityError

    league = League(name="英超")
    db.add(league)
    db.flush()

    match = Match(
        league_id=league.id,
        home_team="H",
        away_team="A",
        match_date=datetime(2026, 5, 1, 22, 0, 0),
        status="scheduled",
    )
    db.add(match)
    db.flush()

    cfg = ModelConfig(
        name="default",
        weights_json={"euro": 1.0},
        thresholds_json={"min": 6},
        kelly_bands_json={"low": {"kelly_pct": 0.005}},
    )
    db.add(cfg)
    db.flush()

    s1 = MatchScore(match_id=match.id, model_config_id=cfg.id, total_score=70)
    db.add(s1)
    db.commit()

    s2 = MatchScore(match_id=match.id, model_config_id=cfg.id, total_score=75)
    db.add(s2)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    else:
        raise AssertionError("expected IntegrityError on duplicate (match, config)")

    assert db.query(MatchScore).count() == 1


def test_backtest_session_has_new_fields(db: Session):
    cfg = ModelConfig(
        name="default",
        weights_json={"euro": 25},
        thresholds_json={"recommend_total_score": 84},
        kelly_bands_json={},
    )
    db.add(cfg)
    db.flush()

    bt = BacktestSession(
        model_config_id=cfg.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 30),
        total_bets=10,
        hit_count=6,
        hit_rate=Decimal("0.60"),
        roi=Decimal("0.18"),
        profit_loss=Decimal("180.00"),
        mode="both",
        initial_capital=Decimal("10000.00"),
        kelly_profit_loss=Decimal("150.00"),
        kelly_roi=Decimal("0.015"),
        equity_curve=[{"date": "2026-04-01", "pnl_fixed": 1.4, "pnl_kelly": 150.0}],
    )
    db.add(bt)
    db.commit()

    fetched = db.query(BacktestSession).one()
    assert fetched.mode == "both"
    assert fetched.initial_capital == Decimal("10000.00")
    assert fetched.kelly_profit_loss == Decimal("150.00")
    assert fetched.equity_curve == [
        {"date": "2026-04-01", "pnl_fixed": 1.4, "pnl_kelly": 150.0}
    ]

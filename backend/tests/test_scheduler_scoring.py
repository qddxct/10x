from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from app.models import (
    Base,
    League,
    Match,
    MatchOdds,
    MatchScore,
    MatchTeamStats,
    ModelConfig,
)
from app.scheduler.jobs import JOB_REGISTRY, run_scoring_job
from app.scripts.seed import DEFAULT_KELLY_BANDS, DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _make_engine_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine, factory


def _seed(session: Session) -> ModelConfig:
    cfg = ModelConfig(
        name="default",
        weights_json=dict(DEFAULT_WEIGHTS),
        thresholds_json=dict(DEFAULT_THRESHOLDS),
        kelly_bands_json=dict(DEFAULT_KELLY_BANDS),
    )
    session.add(cfg)
    session.flush()

    lg = League(name="英超")
    session.add(lg)
    session.flush()

    match = Match(
        league_id=lg.id,
        home_team="H",
        away_team="A",
        match_date=datetime.utcnow() + timedelta(hours=2),
        status="scheduled",
    )
    session.add(match)
    session.flush()

    session.add(
        MatchOdds(
            match_id=match.id,
            source="sporttery",
            win_odds=Decimal("2.50"),
            draw_odds=Decimal("3.10"),
            lose_odds=Decimal("2.60"),
            draw_handicap_odds=Decimal("3.60"),
            asian_handicap="平手",
            total_goals=Decimal("2.25"),
            scraped_at=datetime.utcnow(),
        )
    )
    session.add(
        MatchTeamStats(
            match_id=match.id,
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
    )
    session.commit()
    return cfg


def test_scoring_job_is_registered():
    assert "scoring" in JOB_REGISTRY


def test_run_scoring_job_persists_scores():
    engine, factory = _make_engine_factory()
    with factory() as db:
        _seed(db)

    outcome = run_scoring_job(factory)
    assert outcome.status == "success"
    assert outcome.records == 1

    with factory() as db:
        assert db.query(MatchScore).count() == 1

    engine.dispose()


def test_run_scoring_job_fails_without_config():
    engine, factory = _make_engine_factory()
    outcome = run_scoring_job(factory)
    assert outcome.status == "failed"
    assert "ModelConfig" in (outcome.error or "")
    engine.dispose()


def test_run_scoring_job_uses_provided_config():
    engine, factory = _make_engine_factory()
    with factory() as db:
        cfg = _seed(db)

    with patch("app.scheduler.jobs.ScoringService") as svc_cls:
        instance = svc_cls.return_value
        instance.compute_for_date.return_value = ["x", "y"]
        outcome = run_scoring_job(factory, model_config_id=cfg.id)
        assert outcome.status == "success"
        assert outcome.records == 2
        assert instance.compute_for_date.called
        args, _kwargs = instance.compute_for_date.call_args
        assert args[1] == cfg.id

    engine.dispose()

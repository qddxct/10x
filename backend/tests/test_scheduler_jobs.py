from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from app.models import Base, League, Match, MatchTeamStats, ModelConfig
from app.scheduler.jobs import (
    JOB_REGISTRY,
    find_match_ids_needing_stats,
    run_schedule_job,
    run_team_stats_job,
)
from app.scheduler.main import build_scheduler, load_schedule_config
from app.scrapers.base import ScraperOutcome
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _seed_match(
    db: Session,
    sporttery_id: str,
    *,
    match_date: datetime,
    match_id: int,
    round_: str = "周一001",
) -> Match:
    league = League(name="英超")
    db.add(league)
    db.flush()
    m = Match(
        id=match_id,
        league_id=league.id,
        sporttery_match_id=sporttery_id,
        home_team="H",
        away_team="A",
        round=round_,
        match_date=match_date,
        status="scheduled",
    )
    db.add(m)
    db.commit()
    return m


def test_job_registry_lists_all_jobs():
    assert set(JOB_REGISTRY) == {"schedule", "result", "odds", "team_stats", "scoring"}


def test_run_schedule_job_calls_runner(session_factory):
    fake_outcome = ScraperOutcome(status="success", records=3, error=None)
    with patch("app.scheduler.jobs.ScrapeRunner") as MockRunner, patch(
        "app.scheduler.jobs.SportterySchedule"
    ) as MockSchedule, patch("app.scheduler.jobs.Titan007Odds") as MockOdds, patch(
        "app.scheduler.jobs.run_team_stats_job",
        return_value=ScraperOutcome(status="success", records=4, error=None),
    ) as MockStatsJob:
        MockRunner.return_value.execute.return_value = fake_outcome
        outcome = run_schedule_job(session_factory)

    assert outcome.status == "success"
    assert outcome.records == 10
    MockSchedule.assert_called_once()
    MockOdds.assert_called_once()
    MockStatsJob.assert_called_once_with(session_factory, days_ahead=7)
    assert MockRunner.return_value.execute.call_count == 2


def test_find_match_ids_returns_only_scheduled_without_stats(session_factory):
    with session_factory() as db:
        now = datetime.utcnow()
        a = _seed_match(
            db,
            "M1",
            match_date=now + timedelta(days=1),
            match_id=202604271001,
            round_="周一001",
        )
        _seed_match(
            db,
            "M2",
            match_date=now + timedelta(days=10),
            match_id=202604271002,
            round_="周一002",
        )  # too far
        c = _seed_match(
            db,
            "M3",
            match_date=now + timedelta(days=2),
            match_id=202604271003,
            round_="周一003",
        )

        db.add(MatchTeamStats(match_id=a.id, scraped_at=now))
        db.commit()

        mids = find_match_ids_needing_stats(db, days_ahead=3, now=now)
        assert mids == [c.id]


def test_run_team_stats_job_partial_when_no_candidates(session_factory):
    with patch("app.scheduler.jobs.Titan007AnalysisStats") as MockScraper:
        outcome = run_team_stats_job(session_factory)
    assert outcome.status == "partial"
    assert outcome.records == 0
    MockScraper.assert_not_called()


def test_run_team_stats_job_uses_titan007_analysis_stats(session_factory):
    with session_factory() as db:
        now = datetime.utcnow()
        match = _seed_match(
            db,
            "M1",
            match_date=now + timedelta(days=1),
            match_id=202604271001,
            round_="周一001",
        )

    fake_outcome = ScraperOutcome(status="success", records=1, error=None)
    with patch("app.scheduler.jobs.ScrapeRunner") as MockRunner, patch(
        "app.scheduler.jobs.Titan007AnalysisStats"
    ) as MockScraper:
        MockRunner.return_value.execute.return_value = fake_outcome
        outcome = run_team_stats_job(session_factory, days_ahead=3)

    assert outcome is fake_outcome
    MockScraper.assert_called_once()
    assert MockScraper.call_args.kwargs["match_ids"] == [match.id]


def test_load_schedule_config_uses_defaults_when_no_config(session_factory):
    with session_factory() as db:
        cfg = load_schedule_config(db)
    assert cfg["schedule"] == {"hour": 8, "minute": 30}
    assert cfg["result"] == {"hour": 23, "minute": 30}
    assert "odds" in cfg
    assert "team_stats" in cfg


def test_load_schedule_config_merges_overrides(session_factory):
    with session_factory() as db:
        db.add(
            ModelConfig(
                name="test",
                weights_json={},
                thresholds_json={},
                kelly_bands_json={},
                scrape_schedule_json={"jobs": {"schedule": {"hour": 7, "minute": 0}}},
            )
        )
        db.commit()
        cfg = load_schedule_config(db)

    assert cfg["schedule"] == {"hour": 7, "minute": 0}
    assert cfg["result"] == {"hour": 23, "minute": 30}


def test_build_scheduler_registers_all_jobs(session_factory):
    cfg = {
        "schedule": {"hour": 8, "minute": 30},
        "result": {"hour": 23, "minute": 30},
        "odds": {"hour": "*/2", "minute": 15},
        "team_stats": {"hour": 9, "minute": 0},
    }
    scheduler = build_scheduler(session_factory, cfg)
    jobs = scheduler.get_jobs()
    ids = {j.id for j in jobs}
    assert ids == {"schedule", "result", "odds", "team_stats", "scoring"}

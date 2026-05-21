"""Scheduler job callables wrapping each scraper through ScrapeRunner."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.tz import now_beijing, today_beijing
from app.engine.service import ScoringService
from app.models.match import SportteryMatch
from app.models.team_stats import SportteryMatchTeamStats
from app.scrapers.base import ScraperOutcome
from app.scrapers.sporttery.result import SportteryResult
from app.scrapers.sporttery.schedule import SportterySchedule
from app.scrapers.titan007.analysis_stats import Titan007AnalysisStats
from app.scrapers.titan007.odds import Titan007Odds
from app.services import model_config as mc_svc
from app.services.scrape_runner import ScrapeRunner

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


def run_schedule_job(session_factory: SessionFactory) -> ScraperOutcome:
    """赛程 → 赔率 → 球队统计, 一条龙抓取。"""
    with session_factory() as db:
        schedule_out = ScrapeRunner(db).execute(SportterySchedule(db=db))

    with session_factory() as db:
        odds_out = ScrapeRunner(db).execute(Titan007Odds(db=db))
    logger.info("schedule chain: odds %s (%d)", odds_out.status, odds_out.records)

    stats_out = run_team_stats_job(session_factory, days_ahead=7)
    logger.info("schedule chain: team_stats %s (%d)", stats_out.status, stats_out.records)

    total = schedule_out.records + odds_out.records + stats_out.records
    errors = [
        e for e in [schedule_out.error, odds_out.error, stats_out.error] if e
    ]
    status = "failed" if schedule_out.status == "failed" else "success"
    return ScraperOutcome(
        status=status,
        records=total,
        error="; ".join(errors) if errors else None,
    )


def run_result_job(session_factory: SessionFactory) -> ScraperOutcome:
    with session_factory() as db:
        return ScrapeRunner(db).execute(SportteryResult(db=db))


def run_odds_job(session_factory: SessionFactory) -> ScraperOutcome:
    with session_factory() as db:
        return ScrapeRunner(db).execute(Titan007Odds(db=db))


def find_match_ids_needing_stats(
    db: Session, *, days_ahead: int = 3, now: datetime | None = None
) -> list[int]:
    now = now or now_beijing()
    until = now + timedelta(days=days_ahead)
    rows = (
        db.query(SportteryMatch.id)
        .outerjoin(SportteryMatchTeamStats, SportteryMatchTeamStats.match_id == SportteryMatch.id)
        .filter(
            SportteryMatch.status == "scheduled",
            SportteryMatch.match_date >= now,
            SportteryMatch.match_date <= until,
            SportteryMatchTeamStats.id.is_(None),
            SportteryMatch.round.isnot(None),
        )
        .all()
    )
    return [r.id for r in rows]


def run_team_stats_job(
    session_factory: SessionFactory, *, days_ahead: int = 3
) -> ScraperOutcome:
    with session_factory() as db:
        match_ids = find_match_ids_needing_stats(db, days_ahead=days_ahead)
        if not match_ids:
            logger.info("no matches need team stats refresh")
            return ScraperOutcome(status="partial", records=0, error=None)
        return ScrapeRunner(db).execute(Titan007AnalysisStats(db=db, match_ids=match_ids))


def run_scoring_job(
    session_factory: SessionFactory, *, model_config_id: int | None = None
) -> ScraperOutcome:
    with session_factory() as db:
        cfg_id = model_config_id
        if cfg_id is None:
            cfg = mc_svc.resolve_default(db)
            if cfg is None:
                return ScraperOutcome(
                    status="failed", records=0, error="no ModelConfig"
                )
            cfg_id = cfg.id
        today = today_beijing()
        tomorrow = today + timedelta(days=1)
        results = ScoringService(db).compute_for_date(today, cfg_id)
        results += ScoringService(db).compute_for_date(tomorrow, cfg_id)
        return ScraperOutcome(status="success", records=len(results), error=None)


JOB_REGISTRY: dict[str, Callable[[SessionFactory], ScraperOutcome]] = {
    "schedule": run_schedule_job,
    "result": run_result_job,
    "odds": run_odds_job,
    "team_stats": run_team_stats_job,
    "scoring": run_scoring_job,
}

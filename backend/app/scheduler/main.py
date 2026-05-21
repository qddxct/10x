"""Scheduler entrypoint: load cron schedule from ModelConfig and run jobs."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import engine
from app.scheduler.jobs import JOB_REGISTRY, SessionFactory
from app.services import model_config as mc_svc

logger = logging.getLogger(__name__)

DEFAULT_CRONS: dict[str, dict[str, int | str]] = {
    "schedule": {"hour": 8, "minute": 30},
    "result": {"hour": 23, "minute": 30},
    "odds": {"hour": "*/2", "minute": 15},
    "team_stats": {"hour": 9, "minute": 0},
    "scoring": {"hour": 9, "minute": 15},
}


def _job_wrapper(
    job_name: str,
    fn: Callable[[SessionFactory], Any],
    session_factory: SessionFactory,
) -> Callable[[], None]:
    def _runner() -> None:
        try:
            outcome = fn(session_factory)
            logger.info(
                "job=%s status=%s records=%d", job_name, outcome.status, outcome.records
            )
        except Exception:
            logger.exception("job=%s crashed unexpectedly", job_name)

    _runner.__name__ = f"run_{job_name}"
    return _runner


def load_schedule_config(db: Session) -> dict[str, dict[str, int | str]]:
    cfg = mc_svc.resolve_default(db)
    overrides = {}
    if cfg is not None and cfg.scrape_schedule_json:
        overrides = cfg.scrape_schedule_json.get("jobs") or {}
    return {
        name: {**DEFAULT_CRONS[name], **overrides.get(name, {})}
        for name in JOB_REGISTRY
    }


def build_scheduler(
    session_factory: SessionFactory,
    schedule_config: dict[str, dict[str, int | str]],
    *,
    timezone: str = "Asia/Shanghai",
) -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=timezone)
    for job_name, fn in JOB_REGISTRY.items():
        cron_spec = schedule_config.get(job_name) or DEFAULT_CRONS[job_name]
        scheduler.add_job(
            _job_wrapper(job_name, fn, session_factory),
            CronTrigger(**cron_spec, timezone=timezone),
            id=job_name,
            replace_existing=True,
        )
        logger.info("registered job=%s cron=%s", job_name, cron_spec)
    return scheduler


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as db:
        schedule_config = load_schedule_config(db)
    scheduler = build_scheduler(SessionLocal, schedule_config)
    logger.info("scheduler starting")
    scheduler.start()


if __name__ == "__main__":
    main()

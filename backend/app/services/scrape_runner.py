"""Scrape runner: wraps Scraper.run() with ScrapeLog bookkeeping."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.tz import now_beijing
from app.models.scrape_log import ScrapeLog
from app.scrapers.base import Scraper, ScraperOutcome

logger = logging.getLogger(__name__)


class ScrapeRunner:
    def __init__(self, db: Session):
        self._db = db

    def execute(self, scraper: Scraper) -> ScraperOutcome:
        log = ScrapeLog(
            source=scraper.source,
            job_name=scraper.name,
            status="running",
            started_at=now_beijing(),
            records_count=0,
        )
        self._db.add(log)
        self._db.commit()
        self._db.refresh(log)

        outcome = scraper.run()

        log.status = outcome.status
        log.records_count = outcome.records
        log.error_message = outcome.error
        log.finished_at = now_beijing()
        self._db.add(log)
        self._db.commit()

        logger.info(
            "scrape job=%s source=%s status=%s records=%d",
            scraper.name,
            scraper.source,
            outcome.status,
            outcome.records,
        )
        return outcome

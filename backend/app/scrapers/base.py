"""Scraper base class and outcome primitives.

Each concrete scraper is expected to implement three stages:

1. :meth:`Scraper.fetch` — pull raw bytes/text from a remote source.
2. :meth:`Scraper.parse` — turn raw into a list of normalized row dicts.
3. :meth:`Scraper.persist` — write rows into the database, returning the
   count of rows actually persisted.

The :meth:`Scraper.run` helper coordinates the three stages and produces a
:class:`ScraperOutcome` that can be written back to a ``scrape_logs`` row.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

ScrapeSource = Literal["sporttery", "titan007", "other"]
VALID_SOURCES: set[str] = {"sporttery", "titan007", "other"}
ScrapeStatus = Literal["success", "failed", "partial"]


class ScrapeError(Exception):
    """Raised by scrapers when fetch/parse fails in a way worth surfacing.

    Carries enough context (URL + HTTP status + message) to help operators
    diagnose problems from the scrape log UI.
    """

    def __init__(self, url: str, status: int | None, message: str) -> None:
        self.url = url
        self.status = status
        self.message = message
        super().__init__(f"ScrapeError url={url} status={status} message={message}")


@dataclass(frozen=True)
class ScraperOutcome:
    status: ScrapeStatus
    records: int
    error: str | None


class Scraper(ABC):
    """Abstract scraper base."""

    name: str
    source: ScrapeSource

    @abstractmethod
    def fetch(self) -> str: ...

    @abstractmethod
    def parse(self, raw: str) -> list[dict]: ...

    @abstractmethod
    def persist(self, rows: list[dict]) -> int: ...

    def run(self) -> ScraperOutcome:
        if self.source not in VALID_SOURCES:
            raise ValueError(f"invalid scraper source: {self.source!r}")

        try:
            raw = self.fetch()
            rows = self.parse(raw)
        except Exception as err:
            logger.exception("scraper fetch/parse failed name=%s", self.name)
            return ScraperOutcome(status="failed", records=0, error=str(err))

        try:
            persisted = self.persist(rows)
        except Exception as err:
            logger.exception("scraper persist failed name=%s", self.name)
            return ScraperOutcome(status="failed", records=0, error=str(err))

        if persisted == 0:
            return ScraperOutcome(status="partial", records=0, error=None)
        return ScraperOutcome(status="success", records=persisted, error=None)

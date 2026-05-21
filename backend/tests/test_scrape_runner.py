from __future__ import annotations

import pytest
from app.models import Base
from app.models.scrape_log import ScrapeLog
from app.scrapers.base import ScrapeError, Scraper
from app.services.scrape_runner import ScrapeRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class _Ok(Scraper):
    name = "ok_job"
    source = "sporttery"

    def fetch(self) -> str:
        return "raw"

    def parse(self, raw: str) -> list[dict]:
        return [{"a": 1}]

    def persist(self, rows: list[dict]) -> int:
        return len(rows)


class _Empty(Scraper):
    name = "empty_job"
    source = "titan007"

    def fetch(self) -> str:
        return ""

    def parse(self, raw: str) -> list[dict]:
        return []

    def persist(self, rows: list[dict]) -> int:
        return 0


class _Boom(Scraper):
    name = "boom_job"
    source = "sporttery"

    def fetch(self) -> str:
        raise ScrapeError("http://x", 500, "kaboom")

    def parse(self, raw: str) -> list[dict]:
        return []

    def persist(self, rows: list[dict]) -> int:
        return 0


def test_runner_logs_success(db: Session):
    outcome = ScrapeRunner(db).execute(_Ok())
    assert outcome.status == "success"
    assert outcome.records == 1

    log = db.query(ScrapeLog).one()
    assert log.source == "sporttery"
    assert log.job_name == "ok_job"
    assert log.status == "success"
    assert log.records_count == 1
    assert log.started_at is not None
    assert log.finished_at is not None
    assert log.error_message is None


def test_runner_logs_partial(db: Session):
    outcome = ScrapeRunner(db).execute(_Empty())
    assert outcome.status == "partial"

    log = db.query(ScrapeLog).one()
    assert log.status == "partial"
    assert log.records_count == 0


def test_runner_logs_failed_with_error(db: Session):
    outcome = ScrapeRunner(db).execute(_Boom())
    assert outcome.status == "failed"

    log = db.query(ScrapeLog).one()
    assert log.status == "failed"
    assert log.records_count == 0
    assert "kaboom" in (log.error_message or "")
    assert log.finished_at is not None

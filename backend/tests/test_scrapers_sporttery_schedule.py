from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from app.models import Base, League, Match
from app.scrapers.sporttery.schedule import SportterySchedule, parse_schedule
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

FIXTURE = Path(__file__).parent / "fixtures" / "sporttery_schedule.html"


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


def test_parse_returns_three_rows_with_required_fields():
    rows = parse_schedule(FIXTURE.read_text(encoding="utf-8"))
    assert len(rows) == 3
    first = rows[0]
    assert first["sporttery_match_id"] == "周一001"
    assert first["home_team"] == "阿森纳"
    assert first["away_team"] == "切尔西"
    assert first["league_name"] == "英超"
    assert first["match_date"] == datetime(2026, 5, 1, 22, 0)


def test_persist_upserts_league_and_match(db: Session):
    scraper = SportterySchedule(db=db, raw=FIXTURE.read_text(encoding="utf-8"))
    outcome = scraper.run()
    assert outcome.status == "success"
    assert outcome.records == 3

    assert db.query(League).count() == 2
    assert db.query(Match).count() == 3

    arsenal = db.query(Match).filter(Match.sporttery_match_id == "周一001").one()
    assert arsenal.home_team == "阿森纳"
    assert arsenal.league.name == "英超"


def test_persist_is_idempotent(db: Session):
    raw = FIXTURE.read_text(encoding="utf-8")
    SportterySchedule(db=db, raw=raw).run()
    outcome = SportterySchedule(db=db, raw=raw).run()
    assert outcome.records == 3
    assert db.query(Match).count() == 3
    assert db.query(League).count() == 2


def test_persist_updates_existing_match(db: Session):
    raw = FIXTURE.read_text(encoding="utf-8")
    SportterySchedule(db=db, raw=raw).run()

    updated = raw.replace("阿森纳", "Arsenal FC")
    SportterySchedule(db=db, raw=updated).run()

    m = db.query(Match).filter(Match.sporttery_match_id == "周一001").one()
    assert m.home_team == "Arsenal FC"

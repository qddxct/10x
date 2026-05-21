from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from app.models import Base, League, Match, MatchResult
from app.scrapers.sporttery.result import SportteryResult, parse_result
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

FIXTURE = Path(__file__).parent / "fixtures" / "sporttery_result.html"


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


def _seed_match(db: Session, sporttery_id: str) -> Match:
    league = db.query(League).filter(League.name == "英超").one_or_none()
    if league is None:
        league = League(name="英超")
        db.add(league)
        db.flush()
    m = Match(
        league_id=league.id,
        sporttery_match_id=sporttery_id,
        home_team="H",
        away_team="A",
        match_date=datetime(2026, 5, 1, 22, 0),
        status="scheduled",
    )
    db.add(m)
    db.commit()
    return m


def test_parse_extracts_rows():
    rows = parse_result(FIXTURE.read_text(encoding="utf-8"))
    assert len(rows) == 3
    assert rows[0] == {
        "sporttery_match_id": "周一001",
        "home_score": 2,
        "away_score": 1,
    }


def test_persist_writes_only_for_known_matches(db: Session):
    _seed_match(db, "周一001")
    _seed_match(db, "周一002")

    raw = FIXTURE.read_text(encoding="utf-8")
    outcome = SportteryResult(db=db, raw=raw).run()
    assert outcome.status == "success"
    assert outcome.records == 2

    results = {r.match.sporttery_match_id: r for r in db.query(MatchResult).all()}
    assert set(results) == {"周一001", "周一002"}
    r = results["周一001"]
    assert r.home_score == 2
    assert r.away_score == 1
    assert r.result == "home_win"
    assert results["周一002"].result == "draw"


def test_persist_is_idempotent_and_updates_scores(db: Session):
    _seed_match(db, "周一001")
    raw = FIXTURE.read_text(encoding="utf-8")
    SportteryResult(db=db, raw=raw).run()

    updated = raw.replace(">2<", ">3<", 1)
    SportteryResult(db=db, raw=updated).run()

    r = db.query(MatchResult).one()
    assert r.home_score == 3
    assert r.result == "home_win"


def test_persist_partial_when_no_known_matches(db: Session):
    raw = FIXTURE.read_text(encoding="utf-8")
    outcome = SportteryResult(db=db, raw=raw).run()
    assert outcome.status == "partial"
    assert outcome.records == 0
    assert db.query(MatchResult).count() == 0

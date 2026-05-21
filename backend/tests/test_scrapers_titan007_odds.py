from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from app.models import Base, League, Match, MatchOdds
from app.scrapers.titan007.odds import Titan007Odds, parse_odds
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

FIXTURE = Path(__file__).parent / "fixtures" / "titan007_odds.html"


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


def test_parse_extracts_odds_rows():
    rows = parse_odds(FIXTURE.read_text(encoding="utf-8"))
    assert len(rows) == 2
    r = rows[0]
    assert r["sporttery_match_id"] == "周一001"
    assert r["win_odds"] == Decimal("2.10")
    assert r["draw_odds"] == Decimal("3.40")
    assert r["lose_odds"] == Decimal("3.30")
    assert r["asian_handicap"] == "平手"
    assert r["win_handicap_odds"] == Decimal("0.90")
    assert r["lose_handicap_odds"] == Decimal("0.95")
    assert r["total_goals"] == Decimal("2.5")


def test_persist_inserts_only_for_known_matches(db: Session):
    _seed_match(db, "周一001")
    outcome = Titan007Odds(db=db, raw=FIXTURE.read_text(encoding="utf-8")).run()
    assert outcome.status == "success"
    assert outcome.records == 1

    rows = db.query(MatchOdds).all()
    assert len(rows) == 1
    assert rows[0].source == "titan007"
    assert rows[0].win_odds == Decimal("2.100")
    assert rows[0].asian_handicap == "平手"


def test_persist_is_idempotent_and_updates(db: Session):
    _seed_match(db, "周一001")
    raw = FIXTURE.read_text(encoding="utf-8")
    Titan007Odds(db=db, raw=raw).run()
    updated = raw.replace("2.10", "2.25")
    Titan007Odds(db=db, raw=updated).run()

    assert db.query(MatchOdds).count() == 1
    refreshed = db.query(MatchOdds).one()
    assert refreshed.win_odds == Decimal("2.250")


def test_persist_partial_when_no_known_matches(db: Session):
    outcome = Titan007Odds(db=db, raw=FIXTURE.read_text(encoding="utf-8")).run()
    assert outcome.status == "partial"
    assert db.query(MatchOdds).count() == 0

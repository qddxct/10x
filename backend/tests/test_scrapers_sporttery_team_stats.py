from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from app.models import Base, League, Match, MatchTeamStats
from app.scrapers.sporttery.team_stats import (
    SportteryTeamStats,
    build_detail_url,
    parse_team_stats,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

FIXTURE = Path(__file__).parent / "fixtures" / "sporttery_team_stats.html"


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


def test_build_detail_url():
    url = build_detail_url("2039239")
    assert url == ("https://www.sporttery.cn/jc/zqdz/index.html?showType=2&mid=2039239")


def test_parse_extracts_home_away_stats():
    stats = parse_team_stats(FIXTURE.read_text(encoding="utf-8"))
    assert stats["home_rank"] == 3
    assert stats["home_season_wins"] == 20
    assert stats["home_season_draws"] == 8
    assert stats["home_season_losses"] == 4
    assert stats["home_home_wins"] == 12
    assert stats["home_home_draws"] == 3
    assert stats["home_home_losses"] == 1
    assert stats["home_recent_form"] == "WWDLW"
    assert stats["away_rank"] == 7
    assert stats["away_season_wins"] == 15
    assert stats["away_away_wins"] == 5
    assert stats["away_away_losses"] == 6
    assert stats["away_recent_form"] == "LDWLD"
    assert stats["h2h_home_wins"] == 4
    assert stats["h2h_draws"] == 2
    assert stats["h2h_away_wins"] == 1


def test_persist_inserts_for_known_match(db: Session):
    _seed_match(db, "2039239")
    html = FIXTURE.read_text(encoding="utf-8")
    fetcher = lambda mid: html  # noqa: E731
    outcome = SportteryTeamStats(db=db, match_ids=["2039239"], fetcher=fetcher).run()
    assert outcome.status == "success"
    assert outcome.records == 1

    row = db.query(MatchTeamStats).one()
    assert row.home_rank == 3
    assert row.away_recent_form == "LDWLD"


def test_persist_is_idempotent_and_updates(db: Session):
    _seed_match(db, "2039239")
    html = FIXTURE.read_text(encoding="utf-8")
    SportteryTeamStats(db=db, match_ids=["2039239"], fetcher=lambda m: html).run()

    updated = html.replace('<span class="rank">3</span>', '<span class="rank">2</span>')
    SportteryTeamStats(db=db, match_ids=["2039239"], fetcher=lambda m: updated).run()

    assert db.query(MatchTeamStats).count() == 1
    assert db.query(MatchTeamStats).one().home_rank == 2


def test_persist_skips_unknown_mid(db: Session):
    html = FIXTURE.read_text(encoding="utf-8")
    outcome = SportteryTeamStats(
        db=db, match_ids=["9999999"], fetcher=lambda m: html
    ).run()
    assert outcome.status == "partial"
    assert db.query(MatchTeamStats).count() == 0

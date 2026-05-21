from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from app.models import Base, League, Match, MatchTeamStats
from app.scrapers.titan007.analysis import TitanTeamStats
from app.scrapers.titan007.analysis_stats import Titan007AnalysisStats
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


def _seed_match(db: Session, *, match_id: int = 202602286002) -> Match:
    league = League(name="日职联")
    db.add(league)
    db.flush()
    match = Match(
        id=match_id,
        league_id=league.id,
        sporttery_match_id="SP-1",
        home_team="浦和红钻",
        away_team="鹿岛鹿角",
        match_date=datetime.now() + timedelta(days=1),
        round="周六002",
        status="scheduled",
    )
    db.add(match)
    db.commit()
    return match


def _stats(home_rank: int = 3) -> TitanTeamStats:
    return TitanTeamStats(
        home_rank=home_rank,
        home_season_wins=4,
        home_season_draws=2,
        home_season_losses=1,
        home_home_wins=3,
        home_home_draws=1,
        home_home_losses=0,
        home_recent_form="WWDLDW",
        away_rank=5,
        away_season_wins=3,
        away_season_draws=3,
        away_season_losses=1,
        away_away_wins=1,
        away_away_draws=2,
        away_away_losses=1,
        away_recent_form="DLWDWD",
        h2h_home_wins=2,
        h2h_draws=3,
        h2h_away_wins=1,
        home_recent_matches_count=6,
        home_recent_goals_for=8,
        home_recent_goals_against=5,
        away_recent_matches_count=6,
        away_recent_goals_for=6,
        away_recent_goals_against=6,
        h2h_matches_count=6,
        h2h_draw_score_count=3,
    )


def test_titan_analysis_stats_fetches_by_titan_mapping_and_upserts(db: Session):
    match = _seed_match(db)
    fetched_ids: list[str] = []
    parsed_calls: list[tuple[str, str, str]] = []

    def mapping_fetcher() -> dict[str, str]:
        return {"周六002": "2915933"}

    def analysis_fetcher(titan_match_id: str) -> str:
        fetched_ids.append(titan_match_id)
        return "<html>analysis</html>"

    def parser(html: str, home_team: str, away_team: str) -> TitanTeamStats:
        parsed_calls.append((html, home_team, away_team))
        return _stats()

    outcome = Titan007AnalysisStats(
        db=db,
        match_ids=[match.id],
        mapping_fetcher=mapping_fetcher,
        analysis_fetcher=analysis_fetcher,
        parser=parser,
    ).run()

    assert outcome.status == "success"
    assert outcome.records == 1
    assert fetched_ids == ["2915933"]
    assert parsed_calls == [("<html>analysis</html>", "浦和红钻", "鹿岛鹿角")]

    row = db.query(MatchTeamStats).filter_by(match_id=match.id).one()
    assert row.home_rank == 3
    assert row.away_rank == 5
    assert row.home_recent_matches_count == 6
    assert row.h2h_draw_score_count == 3


def test_titan_analysis_stats_skips_matches_without_titan_mapping(db: Session):
    match = _seed_match(db)

    outcome = Titan007AnalysisStats(
        db=db,
        match_ids=[match.id],
        mapping_fetcher=lambda: {},
        analysis_fetcher=lambda titan_match_id: "unused",
        parser=lambda html, home_team, away_team: _stats(),
    ).run()

    assert outcome.status == "partial"
    assert outcome.records == 0
    assert db.query(MatchTeamStats).count() == 0


def test_titan_analysis_stats_updates_existing_row(db: Session):
    match = _seed_match(db)
    db.add(MatchTeamStats(match_id=match.id, scraped_at=datetime.utcnow(), home_rank=9))
    db.commit()

    outcome = Titan007AnalysisStats(
        db=db,
        match_ids=[match.id],
        mapping_fetcher=lambda: {"周六002": "2915933"},
        analysis_fetcher=lambda titan_match_id: "<html>analysis</html>",
        parser=lambda html, home_team, away_team: _stats(home_rank=2),
    ).run()

    assert outcome.status == "success"
    row = db.query(MatchTeamStats).filter_by(match_id=match.id).one()
    assert row.home_rank == 2
    assert row.home_recent_form == "WWDLDW"

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import httpx
from app.models.match import SportteryMatch
from app.scrapers.titan007.history import TitanMatch
from app.scripts import backfill
from sqlalchemy.orm import Session


def test_backfill_uses_titan_match_id_for_historical_team_stats(
    db: Session,
    monkeypatch,
):
    calls: list[tuple[int, str]] = []

    def fake_upsert_team_stats(
        db: Session,
        match: SportteryMatch,
        titan_match_id: str,
        client: httpx.Client,
        *,
        delay: float = 0.5,
    ) -> bool:
        calls.append((match.id, titan_match_id))
        return True

    monkeypatch.setattr(backfill, "_upsert_team_stats", fake_upsert_team_stats)

    stats = backfill.upsert_day(
        db,
        date(2026, 2, 28),
        [
            {
                "matchNumStr": "周六002",
                "leagueNameAbbr": "日职联",
                "matchId": "",
                "homeTeam": "浦和红钻",
                "awayTeam": "鹿岛鹿角",
                "matchDate": "2026-02-28",
                "matchResultStatus": "2",
                "sectionsNo999": "1:1",
                "h": "2.30",
                "d": "3.10",
                "a": "3.00",
                "goalLine": "0",
            }
        ],
        [
            TitanMatch(
                match_id="2915933",
                kickoff=datetime(2026, 2, 28, 12, 0),
                status="-1",
                jc_code="周六002",
                sclassid="25",
                home_team="浦和红钻",
                away_team="鹿岛鹿角",
                home_score=1,
                away_score=1,
                home_ht_score=0,
                away_ht_score=0,
                handicap_value=Decimal("0"),
            )
        ],
        [],
        client=httpx.Client(transport=httpx.MockTransport(lambda request: None)),
        stats_delay=0,
    )

    assert stats["team_stats"] == 1
    assert calls == [(202602286002, "2915933")]


def test_backfill_does_not_fetch_historical_stats_without_titan_mapping(
    db: Session,
    monkeypatch,
):
    calls: list[str] = []

    def fake_upsert_team_stats(
        db: Session,
        match: SportteryMatch,
        titan_match_id: str,
        client: httpx.Client,
        *,
        delay: float = 0.5,
    ) -> bool:
        calls.append(titan_match_id)
        return True

    monkeypatch.setattr(backfill, "_upsert_team_stats", fake_upsert_team_stats)

    stats = backfill.upsert_day(
        db,
        date(2026, 2, 28),
        [
            {
                "matchNumStr": "周六002",
                "leagueNameAbbr": "日职联",
                "matchId": "",
                "homeTeam": "浦和红钻",
                "awayTeam": "鹿岛鹿角",
                "matchDate": "2026-02-28",
                "matchResultStatus": "2",
                "sectionsNo999": "1:1",
                "h": "2.30",
                "d": "3.10",
                "a": "3.00",
                "goalLine": "0",
            }
        ],
        [],
        [],
        client=httpx.Client(transport=httpx.MockTransport(lambda request: None)),
        stats_delay=0,
    )

    assert stats["team_stats"] == 0
    assert calls == []

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from app.api.auth import router as auth_router
from app.api.scores import router as scores_router
from app.core.database import get_db
from app.core.security import hash_password
from app.models import (
    Base,
    League,
    Match,
    MatchOdds,
    MatchScore,
    MatchTeamStats,
    ModelConfig,
    User,
)
from app.scripts.seed import DEFAULT_KELLY_BANDS, DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session: Session = TestingSession()

    app = FastAPI()
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(scores_router, prefix="/api/scores")

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)
    try:
        yield client, session
    finally:
        session.close()
        engine.dispose()


def _user(session: Session, *, phone: str, role: str = "member") -> None:
    session.add(
        User(
            phone=phone,
            name="u",
            role=role,
            password_hash=hash_password("Abcd1234"),
        )
    )
    session.commit()


def _auth(client: TestClient, phone: str) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"phone": phone, "password": "Abcd1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _seed_config(session: Session) -> ModelConfig:
    cfg = ModelConfig(
        name="default",
        weights_json=dict(DEFAULT_WEIGHTS),
        thresholds_json=dict(DEFAULT_THRESHOLDS),
        kelly_bands_json=dict(DEFAULT_KELLY_BANDS),
    )
    session.add(cfg)
    session.flush()
    return cfg


def _logical_id(dt: datetime, seq: int = 1) -> int:
    weekday = (dt.weekday() + 1) % 7
    return int(dt.strftime("%Y%m%d") + str(weekday) + f"{seq:03d}")


def _seed_match_with_data(
    session: Session, *, offset_hours: int = 2, league_name: str = "英超"
) -> Match:
    lg = League(name=league_name)
    session.add(lg)
    session.flush()
    match_date = datetime.utcnow() + timedelta(hours=offset_hours)
    match = Match(
        id=_logical_id(match_date),
        league_id=lg.id,
        home_team="H",
        away_team="A",
        match_date=match_date,
        status="scheduled",
        round="周五001",
    )
    session.add(match)
    session.flush()

    session.add(
        MatchOdds(
            match_id=match.id,
            source="sporttery",
            win_odds=Decimal("2.50"),
            draw_odds=Decimal("3.10"),
            lose_odds=Decimal("2.60"),
            handicap_value=Decimal("0.0"),
            draw_handicap_odds=Decimal("3.60"),
            asian_handicap="平手",
            total_goals=Decimal("2.25"),
            scraped_at=datetime.utcnow(),
        )
    )
    session.add(
        MatchTeamStats(
            match_id=match.id,
            home_rank=5,
            away_rank=6,
            home_season_wins=10,
            home_season_draws=8,
            home_season_losses=6,
            away_season_wins=9,
            away_season_draws=9,
            away_season_losses=7,
            home_recent_form="WDDLW",
            away_recent_form="DDWLL",
            scraped_at=datetime.utcnow(),
        )
    )
    session.commit()
    return match


def test_today_requires_auth(ctx):
    client, _ = ctx
    r = client.get("/api/scores/today")
    assert r.status_code == 401


def test_today_returns_scored_matches(ctx):
    client, session = ctx
    _user(session, phone="13800010001", role="admin")
    cfg = _seed_config(session)
    match = _seed_match_with_data(session, offset_hours=24)

    r = client.post(
        "/api/scores/compute",
        headers=_auth(client, "13800010001"),
        params={"model_config_id": cfg.id, "date": match.match_date.date().isoformat()},
    )
    assert r.status_code == 200
    assert r.json()["computed"] == 1

    r = client.get("/api/scores/today", headers=_auth(client, "13800010001"))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["home_team"] == "H"
    assert item["away_team"] == "A"
    assert item["league_name"] == "英超"
    assert item["match_round"] == "周五001"
    assert item["total_score"] > 0


def test_today_excludes_finished_matches(ctx):
    client, session = ctx
    _user(session, phone="13800010007", role="admin")
    cfg = _seed_config(session)
    upcoming = _seed_match_with_data(session, offset_hours=24)
    finished = _seed_match_with_data(session, offset_hours=-24, league_name="西甲")
    finished.status = "finished"
    session.add(
        MatchScore(
            match_id=finished.id,
            model_config_id=cfg.id,
            euro_score=25,
            asian_score=20,
            goals_score=20,
            intent_score=15,
            compression_score=20,
            team_stats_score=20,
            total_score=120,
            bet_type="draw",
            kelly_pct=Decimal("0.0200"),
            is_recommended=True,
        )
    )
    session.commit()

    client.post(
        "/api/scores/compute",
        headers=_auth(client, "13800010007"),
        params={"model_config_id": cfg.id, "date": upcoming.match_date.date().isoformat()},
    )

    r = client.get("/api/scores/today", headers=_auth(client, "13800010007"))

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["match_id"] == upcoming.id


def test_compute_requires_admin(ctx):
    client, session = ctx
    _user(session, phone="13800010002", role="member")
    _seed_config(session)
    _seed_match_with_data(session)

    r = client.post("/api/scores/compute", headers=_auth(client, "13800010002"))
    assert r.status_code == 403


def test_compute_upcoming_scores_for_selected_model(ctx):
    client, session = ctx
    _user(session, phone="13800010008", role="admin")
    cfg = _seed_config(session)
    _seed_match_with_data(session, offset_hours=24)

    r = client.post(
        "/api/scores/compute-upcoming",
        headers=_auth(client, "13800010008"),
        params={"model_config_id": cfg.id},
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["model_config_id"] == cfg.id
    assert body["computed"] == 1
    assert len(body["dates"]) == 1


def test_breakdown_returns_six_dimensions(ctx):
    client, session = ctx
    _user(session, phone="13800010003", role="admin")
    cfg = _seed_config(session)
    _seed_match_with_data(session)
    client.post(
        "/api/scores/compute",
        headers=_auth(client, "13800010003"),
        params={"model_config_id": cfg.id},
    )
    score = session.query(MatchScore).one()

    r = client.get(
        f"/api/scores/{score.id}/breakdown",
        headers=_auth(client, "13800010003"),
    )
    assert r.status_code == 200
    body = r.json()
    names = {p["dimension"] for p in body["parts"]}
    assert names == {
        "euro_score",
        "asian_score",
        "goals_score",
        "intent_score",
        "compression_score",
        "team_stats_score",
    }


def test_update_score_notes_and_bet_amount(ctx):
    client, session = ctx
    _user(session, phone="13800010004", role="admin")
    cfg = _seed_config(session)
    _seed_match_with_data(session)
    client.post(
        "/api/scores/compute",
        headers=_auth(client, "13800010004"),
        params={"model_config_id": cfg.id},
    )
    score = session.query(MatchScore).one()

    r = client.put(
        f"/api/scores/{score.id}",
        headers=_auth(client, "13800010004"),
        json={"notes": "hello", "bet_amount": 100.00, "actual_hit": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["notes"] == "hello"
    assert body["actual_hit"] is True
    assert Decimal(body["bet_amount"]) == Decimal("100.00")


def test_breakdown_404_on_missing_score(ctx):
    client, session = ctx
    _user(session, phone="13800010005", role="admin")
    r = client.get(
        "/api/scores/999/breakdown",
        headers=_auth(client, "13800010005"),
    )
    assert r.status_code == 404


def test_by_date_filters_correctly(ctx):
    client, session = ctx
    _user(session, phone="13800010006", role="admin")
    cfg = _seed_config(session)
    m = _seed_match_with_data(session, offset_hours=24 * 3)
    client.post(
        "/api/scores/compute",
        headers=_auth(client, "13800010006"),
        params={"model_config_id": cfg.id, "date": m.match_date.date().isoformat()},
    )

    r = client.get(
        f"/api/scores/by-date?date={m.match_date.date().isoformat()}",
        headers=_auth(client, "13800010006"),
    )
    assert r.status_code == 200
    assert r.json()["total"] == 1

    other = (m.match_date + timedelta(days=1)).date().isoformat()
    r = client.get(
        f"/api/scores/by-date?date={other}",
        headers=_auth(client, "13800010006"),
    )
    assert r.json()["total"] == 0


def test_default_config_prefers_active(ctx):
    client, session = ctx
    _user(session, phone="13800010020", role="admin")
    old_cfg = _seed_config(session)
    new_cfg = ModelConfig(
        name="v2-active",
        weights_json=dict(DEFAULT_WEIGHTS),
        thresholds_json=dict(DEFAULT_THRESHOLDS),
        kelly_bands_json=dict(DEFAULT_KELLY_BANDS),
        is_active=True,
    )
    session.add(new_cfg)
    session.commit()
    m = _seed_match_with_data(session)

    headers = _auth(client, "13800010020")
    r = client.post(
        "/api/scores/compute",
        headers=headers,
        params={"date": m.match_date.date().isoformat()},
    )
    assert r.status_code == 200, r.text
    assert r.json()["model_config_id"] == new_cfg.id
    assert r.json()["model_config_id"] != old_cfg.id

    scores = session.query(MatchScore).all()
    assert [s.model_config_id for s in scores] == [new_cfg.id]

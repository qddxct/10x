from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

import pytest
from app.api.auth import router as auth_router
from app.api.reviews import router as reviews_router
from app.core.database import get_db
from app.core.security import hash_password
from app.models import (
    Base,
    League,
    Match,
    MatchResult,
    MatchScore,
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
    TS = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session: Session = TS()

    app = FastAPI()
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(reviews_router, prefix="/api/reviews")

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


def _seed_cfg(session: Session) -> ModelConfig:
    cfg = ModelConfig(
        name="default",
        weights_json=dict(DEFAULT_WEIGHTS),
        thresholds_json=dict(DEFAULT_THRESHOLDS),
        kelly_bands_json=dict(DEFAULT_KELLY_BANDS),
        is_active=True,
    )
    session.add(cfg)
    session.flush()
    return cfg


def _seed_finished_with_score(
    session: Session,
    cfg_id: int,
    *,
    match_date: date,
    result: str = "draw",
    handicap_result: str | None = "draw",
    bet_type: str | None = "draw",
    is_recommended: bool = True,
    league_name: str = "英超",
) -> MatchScore:
    lg = session.query(League).filter(League.name == league_name).one_or_none()
    if lg is None:
        lg = League(name=league_name)
        session.add(lg)
        session.flush()

    m = Match(
        league_id=lg.id,
        home_team="H",
        away_team="A",
        match_date=datetime.combine(match_date, time(20, 0)),
        status="finished",
    )
    session.add(m)
    session.flush()

    session.add(
        MatchResult(
            match_id=m.id,
            home_score=1 if result == "home_win" else 0,
            away_score=1 if result == "away_win" else 0,
            result=result,
            handicap_result=handicap_result,
        )
    )
    score = MatchScore(
        match_id=m.id,
        model_config_id=cfg_id,
        total_score=80,
        bet_type=bet_type,
        kelly_pct=Decimal("0.02"),
        is_recommended=is_recommended,
    )
    session.add(score)
    session.commit()
    return score


def test_list_requires_auth(ctx):
    client, _ = ctx
    assert client.get("/api/reviews").status_code == 401


def test_list_returns_finished_matches_with_suggested_hit(ctx):
    client, session = ctx
    _user(session, phone="13800040001", role="admin")
    cfg = _seed_cfg(session)
    s = _seed_finished_with_score(session, cfg.id, match_date=date(2026, 4, 10))

    r = client.get(
        "/api/reviews",
        headers=_auth(client, "13800040001"),
        params={"date_from": "2026-04-01", "date_to": "2026-04-30"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["score_id"] == s.id
    assert item["suggested_actual_hit"] is True
    assert item["home_team"] == "H"
    assert item["league_name"] == "英超"


def test_list_only_recommended_filter(ctx):
    client, session = ctx
    _user(session, phone="13800040002", role="admin")
    cfg = _seed_cfg(session)
    _seed_finished_with_score(
        session, cfg.id, match_date=date(2026, 4, 10), is_recommended=False
    )
    rec = _seed_finished_with_score(
        session, cfg.id, match_date=date(2026, 4, 11), is_recommended=True
    )

    r = client.get(
        "/api/reviews",
        headers=_auth(client, "13800040002"),
        params={
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
            "only_recommended": "true",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["score_id"] == rec.id


def test_get_review_by_id(ctx):
    client, session = ctx
    _user(session, phone="13800040003", role="member")
    cfg = _seed_cfg(session)
    s = _seed_finished_with_score(session, cfg.id, match_date=date(2026, 4, 10))

    r = client.get(f"/api/reviews/{s.id}", headers=_auth(client, "13800040003"))
    assert r.status_code == 200
    assert r.json()["score_id"] == s.id

    r = client.get("/api/reviews/9999", headers=_auth(client, "13800040003"))
    assert r.status_code == 404


def test_patch_requires_admin(ctx):
    client, session = ctx
    _user(session, phone="13800040004", role="member")
    cfg = _seed_cfg(session)
    s = _seed_finished_with_score(session, cfg.id, match_date=date(2026, 4, 10))

    r = client.patch(
        f"/api/reviews/{s.id}",
        headers=_auth(client, "13800040004"),
        json={"actual_hit": True, "bet_amount": "100.00", "notes": "hi"},
    )
    assert r.status_code == 403


def test_patch_admin_updates_fields(ctx):
    client, session = ctx
    _user(session, phone="13800040005", role="admin")
    cfg = _seed_cfg(session)
    s = _seed_finished_with_score(session, cfg.id, match_date=date(2026, 4, 10))

    r = client.patch(
        f"/api/reviews/{s.id}",
        headers=_auth(client, "13800040005"),
        json={"actual_hit": True, "bet_amount": "120.50", "notes": "watched live"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["actual_hit"] is True
    assert Decimal(body["bet_amount"]) == Decimal("120.50")
    assert body["notes"] == "watched live"

    # partial update: keep actual_hit, clear notes by sending null explicitly
    r = client.patch(
        f"/api/reviews/{s.id}",
        headers=_auth(client, "13800040005"),
        json={"notes": None},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["notes"] is None
    assert body["actual_hit"] is True


def test_patch_rejects_negative_bet_amount(ctx):
    client, session = ctx
    _user(session, phone="13800040006", role="admin")
    cfg = _seed_cfg(session)
    s = _seed_finished_with_score(session, cfg.id, match_date=date(2026, 4, 10))
    r = client.patch(
        f"/api/reviews/{s.id}",
        headers=_auth(client, "13800040006"),
        json={"bet_amount": "-10"},
    )
    assert r.status_code == 422


def test_list_rejects_inverted_range(ctx):
    client, session = ctx
    _user(session, phone="13800040007", role="admin")
    _seed_cfg(session)
    r = client.get(
        "/api/reviews",
        headers=_auth(client, "13800040007"),
        params={"date_from": "2026-05-01", "date_to": "2026-04-01"},
    )
    assert r.status_code == 400


def test_suggested_hit_false_when_bet_type_miss(ctx):
    client, session = ctx
    _user(session, phone="13800040008", role="admin")
    cfg = _seed_cfg(session)
    s = _seed_finished_with_score(
        session,
        cfg.id,
        match_date=date(2026, 4, 10),
        result="home_win",
        handicap_result="home_win",
        bet_type="draw",
    )

    r = client.get(f"/api/reviews/{s.id}", headers=_auth(client, "13800040008"))
    assert r.status_code == 200
    assert r.json()["suggested_actual_hit"] is False


def test_patch_optimistic_lock_conflict(ctx):
    import time

    client, session = ctx
    _user(session, phone="13800040009", role="admin")
    cfg = _seed_cfg(session)
    s = _seed_finished_with_score(session, cfg.id, match_date=date(2026, 4, 10))

    # Read the row to capture its current updated_at.
    r = client.get(f"/api/reviews/{s.id}", headers=_auth(client, "13800040009"))
    assert r.status_code == 200
    original_updated_at = r.json()["updated_at"]

    # First writer wins with correct expected_updated_at.
    # SQLite's CURRENT_TIMESTAMP has second precision; sleep briefly to ensure
    # the row's updated_at genuinely advances past `original_updated_at` so the
    # second PATCH sees a mismatch.
    time.sleep(1.1)
    r = client.patch(
        f"/api/reviews/{s.id}",
        headers=_auth(client, "13800040009"),
        json={
            "actual_hit": True,
            "expected_updated_at": original_updated_at,
        },
    )
    assert r.status_code == 200, r.text

    # Second writer uses the same (now stale) timestamp → 409.
    r = client.patch(
        f"/api/reviews/{s.id}",
        headers=_auth(client, "13800040009"),
        json={
            "notes": "from stale client",
            "expected_updated_at": original_updated_at,
        },
    )
    assert r.status_code == 409

    # Without expected_updated_at, behaviour is unchanged (last-write-wins).
    r = client.patch(
        f"/api/reviews/{s.id}",
        headers=_auth(client, "13800040009"),
        json={"notes": "force overwrite"},
    )
    assert r.status_code == 200
    assert r.json()["notes"] == "force overwrite"

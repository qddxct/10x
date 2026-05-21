from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from app.api.auth import router as auth_router
from app.api.backtest import router as backtest_router
from app.core.database import get_db
from app.core.security import hash_password
from app.models import (
    Base,
    League,
    Match,
    MatchOdds,
    MatchResult,
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
    app.include_router(backtest_router, prefix="/api/backtest")

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


def _seed_finished_match(
    session: Session,
    *,
    match_date: date,
    result: str = "draw",
    handicap_result: str | None = "draw",
    league_name: str = "英超",
) -> Match:
    lg = session.query(League).filter(
        League.name == league_name
    ).one_or_none() or League(name=league_name)
    if lg.id is None:
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
        MatchOdds(
            match_id=m.id,
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
            match_id=m.id,
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
    session.add(
        MatchResult(
            match_id=m.id,
            home_score=0 if result == "draw" else (1 if result == "home_win" else 0),
            away_score=0 if result == "draw" else (0 if result == "home_win" else 1),
            result=result,
            handicap_result=handicap_result,
        )
    )
    session.commit()
    return m


def test_create_requires_auth(ctx):
    client, _ = ctx
    r = client.post(
        "/api/backtest",
        json={"date_from": "2026-04-01", "date_to": "2026-04-30"},
    )
    assert r.status_code == 401


def test_create_runs_and_returns_summary(ctx):
    client, session = ctx
    _user(session, phone="13800020001", role="member")
    cfg = _seed_config(session)
    _seed_finished_match(session, match_date=date(2026, 4, 1))
    _seed_finished_match(
        session,
        match_date=date(2026, 4, 2),
        result="home_win",
        handicap_result="home_win",
    )

    r = client.post(
        "/api/backtest",
        headers=_auth(client, "13800020001"),
        json={
            "model_config_id": cfg.id,
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
            "mode": "both",
            "initial_capital": 10000,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] >= 1
    assert body["mode"] == "both"
    assert body["total_bets"] >= 1
    assert body["equity_curve"] is not None


def test_create_rejects_invalid_range(ctx):
    client, session = ctx
    _user(session, phone="13800020002", role="member")
    _seed_config(session)
    r = client.post(
        "/api/backtest",
        headers=_auth(client, "13800020002"),
        json={"date_from": "2026-05-01", "date_to": "2026-04-01"},
    )
    assert r.status_code == 400


def test_create_rejects_too_large_range(ctx):
    client, session = ctx
    _user(session, phone="13800020003", role="member")
    _seed_config(session)
    d1 = date(2026, 1, 1)
    d2 = d1 + timedelta(days=200)
    r = client.post(
        "/api/backtest",
        headers=_auth(client, "13800020003"),
        json={"date_from": d1.isoformat(), "date_to": d2.isoformat()},
    )
    assert r.status_code == 400


def test_list_and_get_backtest(ctx):
    client, session = ctx
    _user(session, phone="13800020004", role="member")
    cfg = _seed_config(session)
    _seed_finished_match(session, match_date=date(2026, 4, 1))

    headers = _auth(client, "13800020004")
    created = client.post(
        "/api/backtest",
        headers=headers,
        json={
            "model_config_id": cfg.id,
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
        },
    ).json()
    bt_id = created["id"]

    lst = client.get("/api/backtest", headers=headers).json()
    assert lst["total"] >= 1
    assert any(it["id"] == bt_id for it in lst["items"])

    one = client.get(f"/api/backtest/{bt_id}", headers=headers)
    assert one.status_code == 200
    assert one.json()["id"] == bt_id


def test_get_missing_returns_404(ctx):
    client, session = ctx
    _user(session, phone="13800020005", role="member")
    headers = _auth(client, "13800020005")
    r = client.get("/api/backtest/9999", headers=headers)
    assert r.status_code == 404


def test_delete_backtest(ctx):
    client, session = ctx
    _user(session, phone="13800020015", role="member")
    cfg = _seed_config(session)
    _seed_finished_match(session, match_date=date(2026, 4, 1))

    headers = _auth(client, "13800020015")
    created = client.post(
        "/api/backtest",
        headers=headers,
        json={
            "model_config_id": cfg.id,
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
        },
    ).json()
    bt_id = created["id"]

    r = client.delete(f"/api/backtest/{bt_id}", headers=headers)
    assert r.status_code == 204

    missing = client.get(f"/api/backtest/{bt_id}", headers=headers)
    assert missing.status_code == 404


def test_compare_two_backtests(ctx):
    client, session = ctx
    _user(session, phone="13800020006", role="member")
    cfg = _seed_config(session)
    _seed_finished_match(session, match_date=date(2026, 4, 1))
    headers = _auth(client, "13800020006")
    a = client.post(
        "/api/backtest",
        headers=headers,
        json={
            "model_config_id": cfg.id,
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
        },
    ).json()
    b = client.post(
        "/api/backtest",
        headers=headers,
        json={
            "model_config_id": cfg.id,
            "date_from": "2026-04-01",
            "date_to": "2026-04-15",
        },
    ).json()
    r = client.get(
        "/api/backtest/compare",
        headers=headers,
        params={"a": a["id"], "b": b["id"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["a"]["id"] == a["id"]
    assert body["b"]["id"] == b["id"]


def test_backtest_visibility_isolated_between_members(ctx):
    client, session = ctx
    _user(session, phone="13800020010", role="member")
    _user(session, phone="13800020011", role="member")
    cfg = _seed_config(session)
    _seed_finished_match(session, match_date=date(2026, 4, 1))

    h1 = _auth(client, "13800020010")
    created = client.post(
        "/api/backtest",
        headers=h1,
        json={
            "model_config_id": cfg.id,
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
        },
    ).json()
    bt_id = created["id"]

    h2 = _auth(client, "13800020011")

    lst = client.get("/api/backtest", headers=h2).json()
    assert all(it["id"] != bt_id for it in lst["items"])

    one = client.get(f"/api/backtest/{bt_id}", headers=h2)
    assert one.status_code == 403

    cmp_ = client.get(
        "/api/backtest/compare",
        headers=h2,
        params={"a": bt_id, "b": bt_id},
    )
    assert cmp_.status_code == 403


def test_backtest_admin_sees_all(ctx):
    client, session = ctx
    _user(session, phone="13800020012", role="member")
    _user(session, phone="13800020013", role="admin")
    cfg = _seed_config(session)
    _seed_finished_match(session, match_date=date(2026, 4, 1))

    h_member = _auth(client, "13800020012")
    created = client.post(
        "/api/backtest",
        headers=h_member,
        json={
            "model_config_id": cfg.id,
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
        },
    ).json()
    bt_id = created["id"]

    h_admin = _auth(client, "13800020013")
    lst = client.get("/api/backtest", headers=h_admin).json()
    assert any(it["id"] == bt_id for it in lst["items"])

    one = client.get(f"/api/backtest/{bt_id}", headers=h_admin)
    assert one.status_code == 200

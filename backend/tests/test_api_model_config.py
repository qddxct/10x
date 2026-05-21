from __future__ import annotations

import pytest
from app.api.auth import router as auth_router
from app.api.model_config import router as mc_router
from app.core.database import get_db
from app.core.security import hash_password
from app.models import Base, User
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
    app.include_router(mc_router, prefix="/api/model-configs")

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
    return {"Authorization": f'Bearer {r.json()["token"]}'}


def _valid_payload(name: str = "v1") -> dict:
    return {
        "name": name,
        "weights_json": dict(DEFAULT_WEIGHTS),
        "thresholds_json": dict(DEFAULT_THRESHOLDS),
        "kelly_bands_json": dict(DEFAULT_KELLY_BANDS),
    }


def test_list_requires_auth(ctx):
    client, _ = ctx
    r = client.get("/api/model-configs")
    assert r.status_code == 401


def test_member_can_read_but_not_write(ctx):
    client, session = ctx
    _user(session, phone="13800030001", role="member")
    h = _auth(client, "13800030001")

    r = client.get("/api/model-configs", headers=h)
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0}

    r = client.post("/api/model-configs", headers=h, json=_valid_payload())
    assert r.status_code == 403


def test_admin_create_and_list(ctx):
    client, session = ctx
    _user(session, phone="13800030010", role="admin")
    h = _auth(client, "13800030010")

    r = client.post("/api/model-configs", headers=h, json=_valid_payload("default"))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "default"
    assert body["is_active"] is False
    assert body["parent_id"] is None

    lst = client.get("/api/model-configs", headers=h).json()
    assert lst["total"] == 1
    assert lst["items"][0]["name"] == "default"


def test_admin_duplicate_name_rejected(ctx):
    client, session = ctx
    _user(session, phone="13800030011", role="admin")
    h = _auth(client, "13800030011")
    client.post("/api/model-configs", headers=h, json=_valid_payload("v1"))
    r = client.post("/api/model-configs", headers=h, json=_valid_payload("v1"))
    assert r.status_code == 400


def test_admin_update_and_validation(ctx):
    client, session = ctx
    _user(session, phone="13800030012", role="admin")
    h = _auth(client, "13800030012")
    created = client.post(
        "/api/model-configs", headers=h, json=_valid_payload("v1")
    ).json()
    cid = created["id"]

    bad = {"weights_json": {"euro": 200, "asian": 1}}
    r = client.patch(f"/api/model-configs/{cid}", headers=h, json=bad)
    assert r.status_code == 422

    r = client.patch(
        f"/api/model-configs/{cid}", headers=h, json={"name": "v1-renamed"}
    )
    assert r.status_code == 200
    assert r.json()["name"] == "v1-renamed"


def test_admin_clone_creates_child(ctx):
    client, session = ctx
    _user(session, phone="13800030013", role="admin")
    h = _auth(client, "13800030013")
    root = client.post(
        "/api/model-configs", headers=h, json=_valid_payload("root")
    ).json()

    r = client.post(
        f'/api/model-configs/{root["id"]}/clone',
        headers=h,
        json={"name": "clone-1"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["parent_id"] == root["id"]
    assert body["name"] == "clone-1"
    assert body["weights_json"] == root["weights_json"]


def test_admin_activate_is_exclusive(ctx):
    client, session = ctx
    _user(session, phone="13800030014", role="admin")
    h = _auth(client, "13800030014")
    a = client.post("/api/model-configs", headers=h, json=_valid_payload("a")).json()
    b = client.post("/api/model-configs", headers=h, json=_valid_payload("b")).json()

    r = client.post(f'/api/model-configs/{a["id"]}/activate', headers=h)
    assert r.status_code == 200
    assert r.json()["is_active"] is True

    r = client.post(f'/api/model-configs/{b["id"]}/activate', headers=h)
    assert r.status_code == 200
    assert r.json()["is_active"] is True

    r = client.get("/api/model-configs/active", headers=h)
    assert r.status_code == 200
    assert r.json()["id"] == b["id"]

    lst = client.get("/api/model-configs", headers=h).json()
    active_ids = [it["id"] for it in lst["items"] if it["is_active"]]
    assert active_ids == [b["id"]]


def test_activate_recomputes_today_scores(ctx):
    """TD-6: activating a config must synchronously (re)score today's matches
    and return scores_recomputed.
    """
    from datetime import datetime, time

    from app.models import League, Match, MatchOdds

    client, session = ctx
    _user(session, phone="13800030020", role="admin")
    h = _auth(client, "13800030020")

    # One ModelConfig (active after first activate call).
    cfg = client.post(
        "/api/model-configs", headers=h, json=_valid_payload("today-rescore")
    ).json()

    # Seed a finished-today match + enough odds so scoring can produce a row.
    lg = League(name="英超")
    session.add(lg)
    session.flush()
    today = datetime.utcnow().date()
    match = Match(
        league_id=lg.id,
        home_team="H",
        away_team="A",
        match_date=datetime.combine(today, time(20, 0)),
        status="scheduled",
    )
    session.add(match)
    session.flush()
    from decimal import Decimal as _D

    session.add(
        MatchOdds(
            match_id=match.id,
            source="sporttery",
            win_odds=_D("2.500"),
            draw_odds=_D("3.200"),
            lose_odds=_D("2.800"),
            asian_handicap="平手",
            total_goals=_D("2.25"),
            scraped_at=datetime.utcnow(),
        )
    )
    session.commit()

    r = client.post(f'/api/model-configs/{cfg["id"]}/activate', headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_active"] is True
    assert body["scores_recomputed"] >= 1


def test_active_endpoint_404_when_none(ctx):
    client, session = ctx
    _user(session, phone="13800030015", role="admin")
    h = _auth(client, "13800030015")
    client.post("/api/model-configs", headers=h, json=_valid_payload("a"))

    r = client.get("/api/model-configs/active", headers=h)
    assert r.status_code == 404


def test_get_missing_404(ctx):
    client, session = ctx
    _user(session, phone="13800030016", role="admin")
    h = _auth(client, "13800030016")
    r = client.get("/api/model-configs/9999", headers=h)
    assert r.status_code == 404


def test_member_read_shows_active_first(ctx):
    client, session = ctx
    _user(session, phone="13800030020", role="admin")
    _user(session, phone="13800030021", role="member")
    h_admin = _auth(client, "13800030020")
    a = client.post(
        "/api/model-configs", headers=h_admin, json=_valid_payload("a")
    ).json()
    b = client.post(
        "/api/model-configs", headers=h_admin, json=_valid_payload("b")
    ).json()
    client.post(f'/api/model-configs/{b["id"]}/activate', headers=h_admin)

    h_member = _auth(client, "13800030021")
    lst = client.get("/api/model-configs", headers=h_member).json()
    assert lst["items"][0]["id"] == b["id"]
    assert lst["items"][0]["is_active"] is True
    assert any(it["id"] == a["id"] for it in lst["items"])

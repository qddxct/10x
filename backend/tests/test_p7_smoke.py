"""P7 end-to-end smoke: admin clones -> activates -> scoring uses new config ->
review round-trip writes actual_hit/bet_amount/notes.
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

import pytest
from app.api.auth import router as auth_router
from app.api.model_config import router as mc_router
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
from app.services import model_config as mc_svc
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
    app.include_router(mc_router, prefix="/api/model-configs")
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


def _user(session: Session, *, phone: str, role: str) -> None:
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


def _seed_default_cfg(session: Session) -> ModelConfig:
    cfg = ModelConfig(
        name="default",
        weights_json=dict(DEFAULT_WEIGHTS),
        thresholds_json=dict(DEFAULT_THRESHOLDS),
        kelly_bands_json=dict(DEFAULT_KELLY_BANDS),
        is_active=True,
    )
    session.add(cfg)
    session.commit()
    return cfg


def _seed_finished_match(session: Session, cfg_id: int, match_date: date) -> MatchScore:
    lg = League(name="英超")
    session.add(lg)
    session.flush()
    m = Match(
        league_id=lg.id,
        home_team="Arsenal",
        away_team="Chelsea",
        match_date=datetime.combine(match_date, time(20, 0)),
        status="finished",
    )
    session.add(m)
    session.flush()
    session.add(
        MatchResult(
            match_id=m.id,
            home_score=1,
            away_score=1,
            result="draw",
            handicap_result="draw",
        )
    )
    score = MatchScore(
        match_id=m.id,
        model_config_id=cfg_id,
        total_score=82,
        bet_type="draw",
        kelly_pct=Decimal("0.03"),
        is_recommended=True,
    )
    session.add(score)
    session.commit()
    return score


def test_p7_full_flow_clone_activate_review(ctx):
    client, session = ctx
    _user(session, phone="13800100001", role="admin")
    _user(session, phone="13800100002", role="member")
    cfg = _seed_default_cfg(session)
    score = _seed_finished_match(session, cfg.id, date(2026, 4, 15))

    admin_h = _auth(client, "13800100001")
    member_h = _auth(client, "13800100002")

    # 1. admin clones default -> new config v2 (inactive)
    r = client.post(
        f"/api/model-configs/{cfg.id}/clone", headers=admin_h, json={"name": "v2"}
    )
    assert r.status_code == 201, r.text
    v2 = r.json()
    assert v2["is_active"] is False
    assert v2["parent_id"] == cfg.id

    # 2. admin edits v2 weights (bump euro)
    new_weights = dict(DEFAULT_WEIGHTS)
    new_weights["euro"] = 30
    r = client.patch(
        f"/api/model-configs/{v2['id']}",
        headers=admin_h,
        json={"weights_json": new_weights},
    )
    assert r.status_code == 200, r.text
    assert r.json()["weights_json"]["euro"] == 30

    # 3. member cannot activate
    r = client.post(f"/api/model-configs/{v2['id']}/activate", headers=member_h)
    assert r.status_code == 403

    # 4. admin activates v2 -> default becomes inactive
    r = client.post(f"/api/model-configs/{v2['id']}/activate", headers=admin_h)
    assert r.status_code == 200
    assert r.json()["is_active"] is True
    # resolve_default now returns v2
    session.expire_all()
    assert mc_svc.resolve_default(session).id == v2["id"]

    # 5. member lists reviews (read-only)
    r = client.get(
        "/api/reviews",
        headers=member_h,
        params={"date_from": "2026-04-01", "date_to": "2026-04-30"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["suggested_actual_hit"] is True

    # 6. member PATCH is forbidden
    r = client.patch(
        f"/api/reviews/{score.id}", headers=member_h, json={"actual_hit": True}
    )
    assert r.status_code == 403

    # 7. admin writes full review
    r = client.patch(
        f"/api/reviews/{score.id}",
        headers=admin_h,
        json={
            "actual_hit": True,
            "bet_amount": "200.00",
            "notes": "clean win",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["actual_hit"] is True
    assert Decimal(body["bet_amount"]) == Decimal("200.00")
    assert body["notes"] == "clean win"

    # 8. /api/model-configs list shows both, v2 active
    r = client.get("/api/model-configs", headers=member_h)
    assert r.status_code == 200
    mapping = {c["id"]: c for c in r.json()["items"]}
    assert mapping[cfg.id]["is_active"] is False
    assert mapping[v2["id"]]["is_active"] is True

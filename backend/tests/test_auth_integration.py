"""End-to-end integration test against the full FastAPI app.

Covers: seed default admin -> login -> /me -> admin-only users list ->
member login -> 403 on admin endpoint -> logout.
"""

from __future__ import annotations

import pytest
from app.core.database import get_db
from app.main import app
from app.models import Base
from app.scripts.seed import ensure_default_admin, ensure_default_config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _override_db():
        session: Session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    with TestingSession() as setup:
        ensure_default_config(setup)
        ensure_default_admin(
            setup, phone="13800000000", name="root", password="Admin@1234"
        )

    app.dependency_overrides[get_db] = _override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_full_auth_flow(client):
    r = client.post(
        "/api/auth/login",
        json={"phone": "13800000000", "password": "Admin@1234"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    admin_headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/auth/me", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["role"] == "admin"

    r = client.post(
        "/api/users/",
        headers=admin_headers,
        json={
            "phone": "13900139000",
            "name": "member1",
            "role": "member",
            "password": "Abcd1234",
        },
    )
    assert r.status_code == 201

    r = client.get("/api/users/", headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2

    r = client.post(
        "/api/auth/login",
        json={"phone": "13900139000", "password": "Abcd1234"},
    )
    assert r.status_code == 200
    member_headers = {"Authorization": f"Bearer {r.json()['token']}"}

    r = client.get("/api/users/", headers=member_headers)
    assert r.status_code == 403

    r = client.post("/api/auth/logout", headers=member_headers)
    assert r.status_code == 204

    r = client.get("/api/auth/me")
    assert r.status_code == 401

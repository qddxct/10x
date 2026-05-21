from __future__ import annotations

import pytest
from app.api.auth import router as auth_router
from app.core.database import get_db
from app.core.security import hash_password
from app.models import Base, User
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

    def _override_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db

    client = TestClient(app, raise_server_exceptions=True)
    try:
        yield client, session
    finally:
        session.close()
        engine.dispose()


def _seed_user(
    session: Session,
    *,
    phone: str = "13800138000",
    password: str = "Abcd1234",
    role: str = "member",
) -> User:
    user = User(
        phone=phone,
        name="tester",
        role=role,
        password_hash=hash_password(password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_login_success_returns_token_and_user(ctx):
    client, session = ctx
    user = _seed_user(session, role="admin")
    r = client.post(
        "/api/auth/login", json={"phone": user.phone, "password": "Abcd1234"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token"] and isinstance(body["token"], str)
    assert body["token_type"] == "bearer"
    assert body["user"]["phone"] == user.phone
    assert body["user"]["role"] == "admin"


def test_login_wrong_password_returns_401(ctx):
    client, session = ctx
    user = _seed_user(session)
    r = client.post(
        "/api/auth/login", json={"phone": user.phone, "password": "Wrong1234"}
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid phone or password"


def test_login_unknown_phone_returns_401(ctx):
    client, _ = ctx
    r = client.post(
        "/api/auth/login", json={"phone": "13900139000", "password": "Abcd1234"}
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid phone or password"


def test_login_invalid_phone_format_returns_422(ctx):
    client, _ = ctx
    r = client.post("/api/auth/login", json={"phone": "abc", "password": "Abcd1234"})
    assert r.status_code == 422


def test_me_requires_auth(ctx):
    client, _ = ctx
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_returns_current_user(ctx):
    client, session = ctx
    user = _seed_user(session)
    login = client.post(
        "/api/auth/login", json={"phone": user.phone, "password": "Abcd1234"}
    ).json()
    token = login["token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["phone"] == user.phone
    assert body["role"] == "member"


def test_logout_returns_204_when_authenticated(ctx):
    client, session = ctx
    user = _seed_user(session)
    login = client.post(
        "/api/auth/login", json={"phone": user.phone, "password": "Abcd1234"}
    ).json()
    r = client.post(
        "/api/auth/logout", headers={"Authorization": f"Bearer {login['token']}"}
    )
    assert r.status_code == 204


def test_logout_requires_auth(ctx):
    client, _ = ctx
    r = client.post("/api/auth/logout")
    assert r.status_code == 401

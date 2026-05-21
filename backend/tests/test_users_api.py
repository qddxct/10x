from __future__ import annotations

import pytest
from app.api.auth import router as auth_router
from app.api.users import router as users_router
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
    app.include_router(users_router, prefix="/api/users")

    def _override_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)
    try:
        yield client, session
    finally:
        session.close()
        engine.dispose()


def _create_user(
    session: Session,
    *,
    phone: str,
    role: str,
    password: str = "Abcd1234",
    name: str = "u",
) -> User:
    u = User(phone=phone, name=name, role=role, password_hash=hash_password(password))
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _token_for(client: TestClient, phone: str, password: str = "Abcd1234") -> str:
    r = client.post("/api/auth/login", json={"phone": phone, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _auth(client: TestClient, phone: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token_for(client, phone)}"}


def test_list_users_requires_admin(ctx):
    client, session = ctx
    _create_user(session, phone="13800000001", role="member")
    r = client.get("/api/users/", headers=_auth(client, "13800000001"))
    assert r.status_code == 403


def test_list_users_unauth_returns_401(ctx):
    client, _ = ctx
    r = client.get("/api/users/")
    assert r.status_code == 401


def test_list_users_admin_sees_all(ctx):
    client, session = ctx
    _create_user(session, phone="13800000001", role="admin")
    _create_user(session, phone="13800000002", role="member")
    r = client.get("/api/users/", headers=_auth(client, "13800000001"))
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    assert {u["phone"] for u in items} == {"13800000001", "13800000002"}


def test_create_user_as_admin(ctx):
    client, session = ctx
    _create_user(session, phone="13800000001", role="admin")
    r = client.post(
        "/api/users/",
        headers=_auth(client, "13800000001"),
        json={
            "phone": "13900139000",
            "name": "new",
            "role": "member",
            "password": "Abcd1234",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["phone"] == "13900139000"
    assert body["role"] == "member"


def test_create_user_duplicate_phone_returns_409(ctx):
    client, session = ctx
    _create_user(session, phone="13800000001", role="admin")
    _create_user(session, phone="13900139000", role="member")
    r = client.post(
        "/api/users/",
        headers=_auth(client, "13800000001"),
        json={
            "phone": "13900139000",
            "name": "dup",
            "role": "member",
            "password": "Abcd1234",
        },
    )
    assert r.status_code == 409


def test_create_user_non_admin_forbidden(ctx):
    client, session = ctx
    _create_user(session, phone="13800000001", role="member")
    r = client.post(
        "/api/users/",
        headers=_auth(client, "13800000001"),
        json={
            "phone": "13900139000",
            "name": "x",
            "role": "member",
            "password": "Abcd1234",
        },
    )
    assert r.status_code == 403


def test_patch_user_update_name_and_role(ctx):
    client, session = ctx
    admin = _create_user(session, phone="13800000001", role="admin")
    target = _create_user(session, phone="13800000002", role="member")
    r = client.patch(
        f"/api/users/{target.id}",
        headers=_auth(client, admin.phone),
        json={"name": "renamed", "role": "admin"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "renamed"
    assert body["role"] == "admin"


def test_patch_user_not_found(ctx):
    client, session = ctx
    _create_user(session, phone="13800000001", role="admin")
    r = client.patch(
        "/api/users/9999",
        headers=_auth(client, "13800000001"),
        json={"name": "x"},
    )
    assert r.status_code == 404


def test_reset_password_as_admin(ctx):
    client, session = ctx
    admin = _create_user(session, phone="13800000001", role="admin")
    target = _create_user(
        session, phone="13800000002", role="member", password="Old12345"
    )
    r = client.post(
        f"/api/users/{target.id}/password",
        headers=_auth(client, admin.phone),
        json={"new_password": "NewPass1"},
    )
    assert r.status_code == 204

    # old password should fail
    bad = client.post(
        "/api/auth/login", json={"phone": target.phone, "password": "Old12345"}
    )
    assert bad.status_code == 401
    ok = client.post(
        "/api/auth/login", json={"phone": target.phone, "password": "NewPass1"}
    )
    assert ok.status_code == 200


def test_delete_user_as_admin(ctx):
    client, session = ctx
    admin = _create_user(session, phone="13800000001", role="admin")
    target = _create_user(session, phone="13800000002", role="member")
    r = client.delete(f"/api/users/{target.id}", headers=_auth(client, admin.phone))
    assert r.status_code == 204
    # ensure gone
    r2 = client.get("/api/users/", headers=_auth(client, admin.phone))
    assert len(r2.json()) == 1


def test_admin_cannot_delete_self(ctx):
    client, session = ctx
    admin = _create_user(session, phone="13800000001", role="admin")
    r = client.delete(f"/api/users/{admin.id}", headers=_auth(client, admin.phone))
    assert r.status_code == 400

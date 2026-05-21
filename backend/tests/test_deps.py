from __future__ import annotations

import pytest
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.security import create_access_token
from app.models import Base, User
from fastapi import Depends, FastAPI
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

    def _override_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db

    @app.get("/whoami")
    def whoami(u: User = Depends(get_current_user)):
        return {"id": u.id, "role": u.role}

    @app.get("/admin")
    def admin_only(u: User = Depends(require_roles("admin"))):
        return {"ok": True, "role": u.role}

    @app.get("/members")
    def members_or_admins(u: User = Depends(require_roles("admin", "member"))):
        return {"role": u.role}

    client = TestClient(app, raise_server_exceptions=True)
    try:
        yield client, session
    finally:
        session.close()
        engine.dispose()


def _create_user(
    session: Session, *, role: str = "member", phone: str = "13800138000"
) -> User:
    user = User(phone=phone, name="tester", role=role, password_hash="x")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_no_auth_header_returns_401(ctx):
    client, _ = ctx
    r = client.get("/whoami")
    assert r.status_code == 401
    assert r.json()["detail"] == "Not authenticated"
    assert r.headers.get("www-authenticate") == "Bearer"


def test_malformed_header_returns_401(ctx):
    client, _ = ctx
    r = client.get("/whoami", headers={"Authorization": "Token abc.def.ghi"})
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"


def test_invalid_token_returns_401(ctx):
    client, _ = ctx
    r = client.get("/whoami", headers={"Authorization": "Bearer garbage.token.value"})
    assert r.status_code == 401


def test_expired_token_returns_401(ctx):
    client, session = ctx
    user = _create_user(session)
    token = create_access_token(subject=user.id, expires_minutes=-1)
    r = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_sub_not_integer_returns_401(ctx):
    client, _ = ctx
    token = create_access_token(subject="not-a-number")
    r = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_user_not_found_returns_401(ctx):
    client, _ = ctx
    token = create_access_token(subject=9999)
    r = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_valid_token_returns_user(ctx):
    client, session = ctx
    user = _create_user(session, role="admin")
    token = create_access_token(subject=user.id, extra={"role": user.role})
    r = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == user.id
    assert body["role"] == "admin"


def test_require_roles_blocks_non_admin(ctx):
    client, session = ctx
    user = _create_user(session, role="member")
    token = create_access_token(subject=user.id)
    r = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Forbidden"


def test_require_roles_allows_admin(ctx):
    client, session = ctx
    user = _create_user(session, role="admin")
    token = create_access_token(subject=user.id)
    r = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_require_roles_multi_role_accepts_member(ctx):
    client, session = ctx
    user = _create_user(session, role="member")
    token = create_access_token(subject=user.id)
    r = client.get("/members", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["role"] == "member"


def test_require_roles_rejects_unlisted_role(ctx):
    client, _ = ctx
    fake_user = User(
        id=1, phone="13800138000", name="x", role="other", password_hash="x"
    )

    client.app.dependency_overrides[get_current_user] = lambda: fake_user
    try:
        r = client.get("/members")
        assert r.status_code == 403
        assert r.json()["detail"] == "Forbidden"
    finally:
        client.app.dependency_overrides.pop(get_current_user, None)

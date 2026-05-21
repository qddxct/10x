from __future__ import annotations

import pytest
from app.cli.create_admin import create_admin
from app.core.security import verify_password
from app.models import Base, User
from app.scripts.seed import ensure_default_admin
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s: Session = TestingSession()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def test_ensure_default_admin_creates_once(session):
    user = ensure_default_admin(
        session, phone="13800000001", name="root", password="Abcd1234"
    )
    assert user.role == "admin"
    assert verify_password("Abcd1234", user.password_hash)

    again = ensure_default_admin(
        session, phone="13800000001", name="root", password="different"
    )
    assert again.id == user.id
    # password stays the original hash (idempotent: no overwrite)
    assert verify_password("Abcd1234", again.password_hash)
    assert not verify_password("different", again.password_hash)

    count = session.query(User).filter(User.phone == "13800000001").count()
    assert count == 1


def test_create_admin_creates_new_user(session):
    user = create_admin(session, phone="13900139000", name="cli", password="NewPass1")
    assert user.role == "admin"
    assert user.name == "cli"
    assert verify_password("NewPass1", user.password_hash)


def test_create_admin_rejects_existing_phone(session):
    create_admin(session, phone="13900139000", name="cli", password="NewPass1")
    with pytest.raises(ValueError):
        create_admin(session, phone="13900139000", name="dup", password="NewPass1")


def test_create_admin_validates_password_policy(session):
    with pytest.raises(ValueError):
        create_admin(session, phone="13900139001", name="x", password="short")
    with pytest.raises(ValueError):
        create_admin(session, phone="13900139001", name="x", password="alllowercase")
    with pytest.raises(ValueError):
        create_admin(session, phone="13900139001", name="x", password="12345678")


def test_create_admin_validates_phone(session):
    with pytest.raises(ValueError):
        create_admin(session, phone="not-a-phone", name="x", password="Abcd1234")

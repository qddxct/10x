from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from app.api.auth import router as auth_router
from app.api.scrape import router as scrape_router
from app.core.database import get_db
from app.core.security import hash_password
from app.models import Base, User
from app.models.scrape_log import ScrapeLog
from app.scrapers.base import ScraperOutcome
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
    app.include_router(scrape_router, prefix="/api/scrape")

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)
    try:
        yield client, session
    finally:
        session.close()
        engine.dispose()


def _create_user(session: Session, *, phone: str, role: str) -> None:
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


def _seed_log(session: Session, **overrides) -> ScrapeLog:
    defaults = dict(
        source="sporttery",
        job_name="schedule",
        status="success",
        started_at=datetime(2026, 4, 21, 8, 30),
        finished_at=datetime(2026, 4, 21, 8, 31),
        records_count=5,
    )
    defaults.update(overrides)
    log = ScrapeLog(**defaults)
    session.add(log)
    session.commit()
    return log


def test_list_jobs_requires_admin(ctx):
    client, session = ctx
    _create_user(session, phone="13800000001", role="member")
    r = client.get("/api/scrape/jobs", headers=_auth(client, "13800000001"))
    assert r.status_code == 403


def test_list_jobs_returns_all_four(ctx):
    client, session = ctx
    _create_user(session, phone="13800000002", role="admin")
    r = client.get("/api/scrape/jobs", headers=_auth(client, "13800000002"))
    assert r.status_code == 200
    names = {j["name"] for j in r.json()}
    assert names == {"schedule", "result", "odds", "team_stats", "scoring"}


def test_list_jobs_includes_last_run_from_scraper_log_names(ctx):
    client, session = ctx
    _create_user(session, phone="13800000012", role="admin")
    _seed_log(
        session,
        job_name="sporttery_schedule",
        started_at=datetime(2026, 4, 21, 8, 30),
        finished_at=datetime(2026, 4, 21, 8, 31),
        records_count=11,
    )

    r = client.get("/api/scrape/jobs", headers=_auth(client, "13800000012"))

    assert r.status_code == 200
    schedule = next(j for j in r.json() if j["name"] == "schedule")
    assert schedule["last_status"] == "success"
    assert schedule["last_records_count"] == 11
    assert schedule["last_finished_at"].startswith("2026-04-21T08:31")


def test_list_logs_filters_and_paginates(ctx):
    client, session = ctx
    _create_user(session, phone="13800000003", role="admin")
    _seed_log(session, status="success", job_name="schedule")
    _seed_log(session, status="failed", job_name="result", source="sporttery")
    _seed_log(session, status="success", job_name="odds", source="titan007")

    r = client.get("/api/scrape/logs", headers=_auth(client, "13800000003"))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3

    r = client.get(
        "/api/scrape/logs?status=failed",
        headers=_auth(client, "13800000003"),
    )
    assert r.json()["total"] == 1

    r = client.get(
        "/api/scrape/logs?source=titan007",
        headers=_auth(client, "13800000003"),
    )
    assert r.json()["total"] == 1

    r = client.get(
        "/api/scrape/logs?limit=1",
        headers=_auth(client, "13800000003"),
    )
    d = r.json()
    assert d["total"] == 3
    assert len(d["items"]) == 1


def test_run_job_unknown_returns_404(ctx):
    client, session = ctx
    _create_user(session, phone="13800000004", role="admin")
    r = client.post(
        "/api/scrape/jobs/bogus/run",
        headers=_auth(client, "13800000004"),
    )
    assert r.status_code == 404


def test_run_job_returns_outcome(ctx):
    client, session = ctx
    _create_user(session, phone="13800000005", role="admin")
    fake = ScraperOutcome(status="success", records=7, error=None)

    with patch.dict(
        "app.api.scrape.JOB_REGISTRY",
        {"schedule": lambda sf: fake},
        clear=False,
    ):
        r = client.post(
            "/api/scrape/jobs/schedule/run",
            headers=_auth(client, "13800000005"),
        )
    assert r.status_code == 200
    body = r.json()
    assert body["job"] == "schedule"
    assert body["status"] == "success"
    assert body["records"] == 7


def test_run_job_rejects_non_admin(ctx):
    client, session = ctx
    _create_user(session, phone="13800000006", role="member")
    r = client.post(
        "/api/scrape/jobs/schedule/run",
        headers=_auth(client, "13800000006"),
    )
    assert r.status_code == 403

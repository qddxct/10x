from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from app.api import research as research_api
from app.api.auth import router as auth_router
from app.api.research import router as research_router
from app.core.database import get_db
from app.core.security import hash_password
from app.models import Base, ModelResearchArtifact, ModelResearchRun, User
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
    app.include_router(research_router, prefix="/api/research")

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)
    try:
        yield client, session
    finally:
        session.close()
        engine.dispose()


def _user(session: Session, *, phone: str) -> None:
    session.add(
        User(
            phone=phone,
            name="researcher",
            role="member",
            password_hash=hash_password("Abcd1234"),
        )
    )
    session.commit()


def _auth(client: TestClient, phone: str) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"phone": phone, "password": "Abcd1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _seed_research_run(session: Session) -> ModelResearchRun:
    run = ModelResearchRun(
        name="v34-combo-selector",
        base_model_config_id=None,
        date_from=date(2024, 9, 28),
        date_to=date(2026, 4, 22),
        random_seed=20260426,
        random_trials=1000,
        status="succeeded",
        summary_json={
            "best_strategy": "frequency_selector",
            "best_strategy_roi": 0.4972,
            "strategy_rules": {
                "combo_odds_range": "10.0-14.0",
                "excluded_leagues": ["德甲", "澳超"],
            },
        },
        report_path="docs/analysis/v34.md",
    )
    session.add(run)
    session.flush()
    session.add_all(
        [
            ModelResearchArtifact(
                run_id=run.id,
                artifact_type="combo_simulation",
                label="frequency_selector",
                payload_json={"strategy": "frequency_selector", "roi": 0.4972},
            ),
            ModelResearchArtifact(
                run_id=run.id,
                artifact_type="random_baseline",
                label="frequency_selector:候选池约束随机",
                payload_json={
                    "strategy": "frequency_selector",
                    "label": "候选池约束随机",
                    "roi_avg": 0.2375,
                    "model_roi_percentile": 0.819,
                },
            ),
            ModelResearchArtifact(
                run_id=run.id,
                artifact_type="random_ticket",
                label="frequency_selector:全市场随机",
                payload_json={
                    "strategy": "frequency_selector",
                    "group_type": "random_control",
                    "control_label": "全市场随机",
                    "ticket_date": "2026-01-02",
                    "combo_odds": 9.6,
                    "stake": 100.0,
                    "is_hit": False,
                    "pnl": -100.0,
                    "legs": [
                        {
                            "match_id": 201,
                            "league": "英冠",
                            "home_team": "随机主队A",
                            "away_team": "随机客队A",
                            "bet_type": "draw",
                            "bet_label": "平",
                            "handicap_value": None,
                            "odds": 3.0,
                            "result_label": "0-1 未命中",
                            "is_hit": False,
                        },
                        {
                            "match_id": 202,
                            "league": "西甲",
                            "home_team": "随机主队B",
                            "away_team": "随机客队B",
                            "bet_type": "draw",
                            "bet_label": "平",
                            "handicap_value": None,
                            "odds": 3.2,
                            "result_label": "1-1 命中",
                            "is_hit": True,
                        },
                    ],
                },
            ),
            ModelResearchArtifact(
                run_id=run.id,
                artifact_type="combo_ticket",
                label="frequency_selector",
                payload_json={
                    "strategy": "frequency_selector",
                    "ticket_date": "2026-01-01",
                    "combo_odds": 11.25,
                    "is_hit": True,
                    "pnl": 1025.0,
                    "legs": [
                        {
                            "match_id": 101,
                            "league": "英冠",
                            "home_team": "主队A",
                            "away_team": "客队A",
                            "bet_type": "draw",
                            "bet_label": "平",
                            "handicap_value": -1.0,
                            "odds": 3.2,
                            "result_label": "1-1 平",
                            "is_hit": True,
                        },
                        {
                            "match_id": 102,
                            "league": "西甲",
                            "home_team": "主队B",
                            "away_team": "客队B",
                            "bet_type": "handicap_draw",
                            "bet_label": "让平 (-1)",
                            "handicap_value": -1.0,
                            "odds": 3.5,
                            "result_label": "2-1 让平",
                            "is_hit": True,
                        },
                    ],
                },
            ),
            ModelResearchArtifact(
                run_id=run.id,
                artifact_type="combo_ticket",
                label="frequency_selector",
                payload_json={
                    "strategy": "frequency_selector",
                    "ticket_date": "2026-01-02",
                    "combo_odds": 9.0,
                    "is_hit": False,
                    "pnl": -100.0,
                    "legs": [
                        {
                            "match_id": 103,
                            "league": "英冠",
                            "home_team": "主队C",
                            "away_team": "客队C",
                            "bet_type": "draw",
                            "bet_label": "平",
                            "handicap_value": None,
                            "odds": 3.0,
                            "result_label": "0-1 未命中",
                            "is_hit": False,
                        },
                        {
                            "match_id": 104,
                            "league": "西甲",
                            "home_team": "主队D",
                            "away_team": "客队D",
                            "bet_type": "draw",
                            "bet_label": "平",
                            "handicap_value": None,
                            "odds": 3.0,
                            "result_label": "2-2 命中",
                            "is_hit": True,
                        },
                    ],
                },
            ),
            ModelResearchArtifact(
                run_id=run.id,
                artifact_type="combo_ticket",
                label="frequency_selector",
                payload_json={
                    "strategy": "frequency_selector",
                    "ticket_date": "2026-01-03",
                    "combo_odds": 8.5,
                    "is_hit": False,
                    "pnl": -100.0,
                    "legs": [
                        {
                            "match_id": 105,
                            "league": "英冠",
                            "home_team": "主队E",
                            "away_team": "客队E",
                            "bet_type": "draw",
                            "bet_label": "平",
                            "handicap_value": None,
                            "odds": 2.8,
                            "result_label": "1-0 未命中",
                            "is_hit": False,
                        },
                        {
                            "match_id": 106,
                            "league": "西甲",
                            "home_team": "主队F",
                            "away_team": "客队F",
                            "bet_type": "draw",
                            "bet_label": "平",
                            "handicap_value": None,
                            "odds": 3.04,
                            "result_label": "0-0 命中",
                            "is_hit": True,
                        },
                    ],
                },
            ),
        ]
    )
    session.commit()
    return run


def test_get_research_detail_groups_artifacts(ctx):
    client, session = ctx
    _user(session, phone="13800030001")
    run = _seed_research_run(session)

    r = client.get(f"/api/research/{run.id}", headers=_auth(client, "13800030001"))

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == run.id
    assert body["summary_json"]["best_strategy"] == "frequency_selector"
    assert body["artifacts"]["combo_simulation"][0]["payload_json"]["roi"] == 0.4972
    assert body["artifacts"]["random_baseline"][0]["payload_json"]["label"] == "候选池约束随机"


def test_get_research_tickets_defaults_to_best_strategy(ctx):
    client, session = ctx
    _user(session, phone="13800030002")
    run = _seed_research_run(session)

    r = client.get(f"/api/research/{run.id}/tickets", headers=_auth(client, "13800030002"))

    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 3
    assert body[0]["strategy"] == "frequency_selector"
    assert body[0]["legs"][0]["bet_label"] == "平"
    assert body[0]["legs"][1]["bet_label"] == "让平 (-1)"


def test_get_research_ticket_groups_returns_model_and_random_controls(ctx):
    client, session = ctx
    _user(session, phone="13800030004")
    run = _seed_research_run(session)

    r = client.get(
        f"/api/research/{run.id}/ticket-groups",
        headers=_auth(client, "13800030004"),
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert [group["group_key"] for group in body] == [
        "model:frequency_selector",
        "random:frequency_selector:全市场随机",
    ]
    assert body[0]["title"] == "模型最佳策略：frequency_selector"  # noqa: RUF001
    assert body[0]["summary"]["ticket_count"] == 3
    assert body[0]["summary"]["stake"] == 300.0
    assert body[0]["summary"]["returns"] == 1125.0
    assert body[0]["summary"]["max_hit_streak"] == 1
    assert body[0]["summary"]["max_miss_streak"] == 2
    assert body[1]["title"] == "对照组：全市场随机"  # noqa: RUF001
    assert body[1]["tickets"][0]["control_label"] == "全市场随机"


def test_get_research_detail_returns_404_for_missing_run(ctx):
    client, session = ctx
    _user(session, phone="13800030003")

    r = client.get("/api/research/999", headers=_auth(client, "13800030003"))

    assert r.status_code == 404


def test_generate_combo_report_rejects_invalid_date_range(ctx):
    client, session = ctx
    _user(session, phone="13800030005")
    payload = {
        "date_from": "2026-04-22",
        "date_to": "2026-03-22",
        "model_name": "empirical-v32-filtered-candidate",
        "random_trials": 1000,
        "random_seed": 20260426,
    }

    r = client.post(
        "/api/research/generate-combo-report",
        json=payload,
        headers=_auth(client, "13800030005"),
    )

    assert r.status_code == 400
    assert "date_from" in r.json()["detail"]


def test_generate_combo_report_creates_run(ctx, monkeypatch):
    client, session = ctx
    _user(session, phone="13800030006")

    result = SimpleNamespace(
        run_id=10,
        report_path="docs/analysis/generated/report.md",
        score_summary={
            "rows": 10,
            "candidates": 4,
            "portfolio": 4,
            "scored_matches": 4,
            "recommended_scores": 4,
            "draw_scores": 3,
            "handicap_draw_scores": 1,
            "replaced_old_scores": 0,
        },
        research_summary={
            "best_strategy": "frequency_selector",
            "best_strategy_combo_count": 2,
            "best_strategy_roi": 0.18,
        },
    )

    def fake_generate(*args, **kwargs):
        assert kwargs["date_from"] == date(2026, 1, 1)
        assert kwargs["date_to"] == date(2026, 1, 31)
        assert kwargs["model_name"] == "empirical-v32-filtered-candidate"
        assert kwargs["random_trials"] == 100
        assert kwargs["random_seed"] == 20260426
        return result

    monkeypatch.setattr(research_api, "generate_user_combo_report", fake_generate)

    r = client.post(
        "/api/research/generate-combo-report",
        json={
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
            "model_name": "empirical-v32-filtered-candidate",
            "random_trials": 100,
            "random_seed": 20260426,
        },
        headers=_auth(client, "13800030006"),
    )

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["run_id"] == 10
    assert body["score_summary"]["recommended_scores"] == 4
    assert body["research_summary"]["best_strategy"] == "frequency_selector"

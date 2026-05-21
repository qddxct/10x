from __future__ import annotations

import pytest
from app.models import Base, ModelConfig
from app.scripts.seed import (
    DEFAULT_CONFIG_NAME,
    V32_CONFIG_NAME,
    ensure_default_config,
    ensure_v32_config,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_ensure_default_config_creates_once(db):
    cfg1 = ensure_default_config(db)
    assert cfg1.name == DEFAULT_CONFIG_NAME
    assert cfg1.weights_json is not None
    assert "euro" in cfg1.weights_json

    cfg2 = ensure_default_config(db)
    assert cfg1.id == cfg2.id

    total = (
        db.query(ModelConfig).filter(ModelConfig.name == DEFAULT_CONFIG_NAME).count()
    )
    assert total == 1


def test_ensure_v32_config_creates_active_candidate(db):
    ensure_default_config(db)
    cfg = ensure_v32_config(db)

    assert cfg.name == V32_CONFIG_NAME
    assert cfg.is_active is True
    assert cfg.thresholds_json["strategy"] == "empirical_v32_filtered"
    assert cfg.thresholds_json["recommend_total_score"] == 108
    assert cfg.kelly_bands_json["hdraw_core"]["kelly_pct"] == 0.015
    assert (
        db.query(ModelConfig)
        .filter(ModelConfig.name == DEFAULT_CONFIG_NAME, ModelConfig.is_active.is_(True))
        .count()
        == 0
    )


def test_ensure_v32_config_is_idempotent(db):
    first = ensure_v32_config(db)
    second = ensure_v32_config(db)

    assert first.id == second.id
    assert db.query(ModelConfig).filter(ModelConfig.name == V32_CONFIG_NAME).count() == 1

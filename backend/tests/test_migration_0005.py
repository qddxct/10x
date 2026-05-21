from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from app.models import ModelConfig
from sqlalchemy.orm import Session

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0005_normalize_legacy_weights.py"
)


def _mig():
    spec = importlib.util.spec_from_file_location("mig_0005", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _insert_config(session: Session, *, name: str, weights: dict) -> int:
    cfg = ModelConfig(
        name=name,
        weights_json=weights,
        thresholds_json={},
        kelly_bands_json={},
    )
    session.add(cfg)
    session.commit()
    return cfg.id


def _weights_of(session: Session, cfg_id: int) -> dict:
    cfg = session.get(ModelConfig, cfg_id)
    assert cfg is not None
    raw = cfg.weights_json
    return json.loads(raw) if isinstance(raw, str) else raw


def test_is_legacy_detects_all_ones():
    m = _mig()
    assert m._is_legacy(
        {
            "euro": 1.0,
            "asian": 1.0,
            "goals": 1.0,
            "intent": 1.0,
            "compression": 1.0,
            "team_stats": 1.0,
        }
    )


def test_is_legacy_rejects_missing_key():
    m = _mig()
    assert not m._is_legacy({"euro": 1.0, "asian": 1.0})


def test_is_legacy_rejects_large_value():
    m = _mig()
    assert not m._is_legacy(
        {
            "euro": 25,
            "asian": 1.0,
            "goals": 1.0,
            "intent": 1.0,
            "compression": 1.0,
            "team_stats": 1.0,
        }
    )


def test_is_legacy_rejects_empty_and_non_dict():
    m = _mig()
    assert not m._is_legacy({})
    assert not m._is_legacy(None)
    assert not m._is_legacy("{}")


def test_upgrade_rewrites_legacy_1_0_weights(db: Session):
    legacy = {
        "euro": 1.0,
        "asian": 1.0,
        "goals": 1.0,
        "intent": 1.0,
        "compression": 1.0,
        "team_stats": 1.0,
    }
    cfg_id = _insert_config(db, name="default", weights=legacy)

    m = _mig()
    conn = db.connection()
    for row_id, weights in m._rows(conn, "model_configs"):
        if m._is_legacy(weights):
            m._update(conn, "model_configs", row_id, dict(m._NEW_WEIGHTS))
    db.commit()
    db.expire_all()

    assert _weights_of(db, cfg_id) == {
        "euro": 25,
        "asian": 20,
        "goals": 20,
        "intent": 15,
        "compression": 20,
        "team_stats": 20,
    }


def test_upgrade_skips_custom_weights(db: Session):
    custom = {
        "euro": 2.0,
        "asian": 1.0,
        "goals": 1.0,
        "intent": 1.0,
        "compression": 1.0,
        "team_stats": 1.0,
    }
    cfg_id = _insert_config(db, name="experimental", weights=dict(custom))

    m = _mig()
    conn = db.connection()
    for row_id, weights in m._rows(conn, "model_configs"):
        if m._is_legacy(weights):
            m._update(conn, "model_configs", row_id, dict(m._NEW_WEIGHTS))
    db.commit()
    db.expire_all()

    assert _weights_of(db, cfg_id) == custom


def test_downgrade_restores_1_0_for_matching_defaults(db: Session):
    new_weights = {
        "euro": 25,
        "asian": 20,
        "goals": 20,
        "intent": 15,
        "compression": 20,
        "team_stats": 20,
    }
    cfg_id = _insert_config(db, name="default", weights=dict(new_weights))

    m = _mig()
    conn = db.connection()
    for row_id, weights in m._rows(conn, "model_configs"):
        if weights == m._NEW_WEIGHTS:
            m._update(conn, "model_configs", row_id, dict(m._LEGACY_WEIGHTS_1_0))
    db.commit()
    db.expire_all()

    restored = _weights_of(db, cfg_id)
    assert all(restored[k] == 1.0 for k in new_weights)

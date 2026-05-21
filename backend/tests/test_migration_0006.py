from __future__ import annotations

from app.models import ModelConfig
from sqlalchemy.orm import Session


def _cfg(name: str = "default") -> ModelConfig:
    return ModelConfig(
        name=name,
        weights_json={
            "euro": 25,
            "asian": 20,
            "goals": 20,
            "intent": 15,
            "compression": 20,
            "team_stats": 20,
        },
        thresholds_json={},
        kelly_bands_json={},
    )


def test_model_config_has_is_active_and_parent(db: Session):
    cfg = _cfg()
    db.add(cfg)
    db.commit()

    fetched = db.query(ModelConfig).one()
    assert fetched.is_active is False
    assert fetched.parent_id is None


def test_model_config_parent_link(db: Session):
    root = _cfg("default")
    db.add(root)
    db.flush()

    clone = _cfg("clone-v1")
    clone.parent_id = root.id
    db.add(clone)
    db.commit()

    got = db.query(ModelConfig).filter(ModelConfig.name == "clone-v1").one()
    assert got.parent_id == root.id
    assert got.parent is not None
    assert got.parent.name == "default"

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ModelConfig


class ModelConfigError(ValueError):
    """Raised on domain-level validation errors (duplicate name, not found)."""


def list_configs(db: Session) -> list[ModelConfig]:
    stmt = select(ModelConfig).order_by(
        ModelConfig.is_active.desc(), ModelConfig.id.desc()
    )
    return list(db.execute(stmt).scalars().all())


def get_config(db: Session, config_id: int) -> ModelConfig:
    cfg = db.get(ModelConfig, config_id)
    if cfg is None:
        raise ModelConfigError(f"ModelConfig {config_id} not found")
    return cfg


def get_active(db: Session) -> ModelConfig | None:
    stmt = select(ModelConfig).where(ModelConfig.is_active.is_(True)).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def resolve_default(db: Session) -> ModelConfig | None:
    """Pick the configuration to use when caller didn't specify an id.

    Preference: active config (``is_active=TRUE``) → oldest by id.
    """
    active = get_active(db)
    if active is not None:
        return active
    stmt = select(ModelConfig).order_by(ModelConfig.id.asc()).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def _ensure_unique_name(
    db: Session, name: str, *, exclude_id: int | None = None
) -> None:
    stmt = select(ModelConfig.id).where(ModelConfig.name == name)
    if exclude_id is not None:
        stmt = stmt.where(ModelConfig.id != exclude_id)
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is not None:
        raise ModelConfigError(f'ModelConfig name "{name}" already exists')


def create_config(
    db: Session,
    *,
    name: str,
    weights_json: dict[str, Any],
    thresholds_json: dict[str, Any],
    kelly_bands_json: dict[str, Any],
    scrape_schedule_json: dict[str, Any] | None = None,
    created_by: int | None = None,
    parent_id: int | None = None,
) -> ModelConfig:
    _ensure_unique_name(db, name)
    cfg = ModelConfig(
        name=name,
        created_by=created_by,
        parent_id=parent_id,
        weights_json=copy.deepcopy(weights_json),
        thresholds_json=copy.deepcopy(thresholds_json),
        kelly_bands_json=copy.deepcopy(kelly_bands_json),
        scrape_schedule_json=(
            copy.deepcopy(scrape_schedule_json)
            if scrape_schedule_json is not None
            else None
        ),
        is_active=False,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def update_config(
    db: Session,
    config_id: int,
    *,
    name: str | None = None,
    weights_json: dict[str, Any] | None = None,
    thresholds_json: dict[str, Any] | None = None,
    kelly_bands_json: dict[str, Any] | None = None,
    scrape_schedule_json: dict[str, Any] | None = None,
    created_by: int | None = None,
) -> ModelConfig:
    """Update config in place.

    Note: Caller is responsible for branching on `is_active` when immutability
    of historical backtest baselines is required. A future enhancement can
    auto-clone when `cfg.is_active` is True.
    """
    cfg = get_config(db, config_id)
    if name is not None and name != cfg.name:
        _ensure_unique_name(db, name, exclude_id=cfg.id)
        cfg.name = name
    if weights_json is not None:
        cfg.weights_json = copy.deepcopy(weights_json)
    if thresholds_json is not None:
        cfg.thresholds_json = copy.deepcopy(thresholds_json)
    if kelly_bands_json is not None:
        cfg.kelly_bands_json = copy.deepcopy(kelly_bands_json)
    if scrape_schedule_json is not None:
        cfg.scrape_schedule_json = copy.deepcopy(scrape_schedule_json)
    db.commit()
    db.refresh(cfg)
    return cfg


def clone_config(
    db: Session,
    config_id: int,
    *,
    new_name: str,
    created_by: int | None = None,
) -> ModelConfig:
    src = get_config(db, config_id)
    _ensure_unique_name(db, new_name)
    clone = ModelConfig(
        name=new_name,
        created_by=created_by,
        parent_id=src.id,
        weights_json=copy.deepcopy(src.weights_json),
        thresholds_json=copy.deepcopy(src.thresholds_json),
        kelly_bands_json=copy.deepcopy(src.kelly_bands_json),
        scrape_schedule_json=(
            copy.deepcopy(src.scrape_schedule_json)
            if src.scrape_schedule_json is not None
            else None
        ),
        is_active=False,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


def activate_config(db: Session, config_id: int) -> ModelConfig:
    """Mark `config_id` as the single active config (atomic swap)."""
    target = get_config(db, config_id)
    db.query(ModelConfig).filter(
        ModelConfig.is_active.is_(True), ModelConfig.id != target.id
    ).update({"is_active": False}, synchronize_session="fetch")
    target.is_active = True
    db.commit()
    db.refresh(target)
    return target

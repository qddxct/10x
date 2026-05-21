"""Seed default data (idempotent).

Run: python -m app.scripts.seed
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.model_config import ModelConfig
from app.models.user import User

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_NAME = "default"
V32_CONFIG_NAME = "empirical-v32-filtered-candidate"

DEFAULT_WEIGHTS: dict[str, Any] = {
    "euro": 25,
    "asian": 20,
    "goals": 20,
    "intent": 15,
    "compression": 20,
    "team_stats": 20,
}

DEFAULT_THRESHOLDS: dict[str, Any] = {
    "min_total_score": 100,
    "recommend_total_score": 104,
    "draw_min_score": 104,
    "handicap_draw_min_score": 104,
    "draw_handicap_abs_max": 0.0,
    "euro_draw_min": 3.10,
    "compression_ratio_min": 0.85,
}

DEFAULT_KELLY_BANDS: dict[str, Any] = {
    "low": {"min_score": 78, "max_score": 84, "kelly_pct": 0.01},
    "mid": {"min_score": 84, "max_score": 96, "kelly_pct": 0.015},
    "high": {"min_score": 96, "max_score": 120, "kelly_pct": 0.02},
}

DEFAULT_SCRAPE_SCHEDULE: dict[str, Any] = {
    "daily": {"hour": 8, "minute": 30},
    "pre_match_refresh_minutes": [120, 60, 30, 10],
}

V32_THRESHOLDS: dict[str, Any] = {
    **DEFAULT_THRESHOLDS,
    "strategy": "empirical_v32_filtered",
    "recommend_total_score": 108,
    "draw_min_score": 108,
    "handicap_draw_min_score": 116,
}

V32_KELLY_BANDS: dict[str, Any] = {
    "draw_core": {"min_score": 108, "max_score": 115, "kelly_pct": 0.010},
    "hdraw_core": {"min_score": 116, "max_score": 120, "kelly_pct": 0.015},
}


def ensure_default_config(db: Session) -> ModelConfig:
    existing = (
        db.query(ModelConfig)
        .filter(ModelConfig.name == DEFAULT_CONFIG_NAME)
        .one_or_none()
    )
    if existing is not None:
        if not existing.is_active and _no_other_active(db, exclude_id=existing.id):
            existing.is_active = True
            db.commit()
            logger.info("promoted default ModelConfig id=%s to active", existing.id)
        else:
            logger.info("default ModelConfig exists id=%s, skip", existing.id)
        return existing

    cfg = ModelConfig(
        name=DEFAULT_CONFIG_NAME,
        created_by=None,
        weights_json=DEFAULT_WEIGHTS,
        thresholds_json=DEFAULT_THRESHOLDS,
        kelly_bands_json=DEFAULT_KELLY_BANDS,
        scrape_schedule_json=DEFAULT_SCRAPE_SCHEDULE,
        is_active=_no_other_active(db, exclude_id=None),
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    logger.info("created default ModelConfig id=%s active=%s", cfg.id, cfg.is_active)
    return cfg


def ensure_v32_config(db: Session) -> ModelConfig:
    existing = (
        db.query(ModelConfig)
        .filter(ModelConfig.name == V32_CONFIG_NAME)
        .one_or_none()
    )
    if existing is not None:
        _activate_only(db, existing)
        logger.info("v32 ModelConfig exists id=%s, active", existing.id)
        return existing

    cfg = ModelConfig(
        name=V32_CONFIG_NAME,
        created_by=None,
        weights_json=DEFAULT_WEIGHTS,
        thresholds_json=V32_THRESHOLDS,
        kelly_bands_json=V32_KELLY_BANDS,
        scrape_schedule_json=DEFAULT_SCRAPE_SCHEDULE,
        is_active=True,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    _activate_only(db, cfg)
    logger.info("created v32 ModelConfig id=%s active=%s", cfg.id, cfg.is_active)
    return cfg


def _activate_only(db: Session, cfg: ModelConfig) -> None:
    db.query(ModelConfig).filter(ModelConfig.id != cfg.id).update({"is_active": False})
    cfg.is_active = True
    db.commit()
    db.refresh(cfg)


def _no_other_active(db: Session, *, exclude_id: int | None) -> bool:
    q = db.query(ModelConfig).filter(ModelConfig.is_active.is_(True))
    if exclude_id is not None:
        q = q.filter(ModelConfig.id != exclude_id)
    return q.count() == 0


def ensure_default_admin(db: Session, *, phone: str, name: str, password: str) -> User:
    existing = db.query(User).filter(User.phone == phone).one_or_none()
    if existing is not None:
        logger.info("default admin exists id=%s, skip", existing.id)
        return existing

    user = User(
        phone=phone,
        name=name,
        role="admin",
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("created default admin id=%s phone=%s", user.id, user.phone)
    return user


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    settings = get_settings()
    with SessionLocal() as db:
        ensure_default_config(db)
        ensure_v32_config(db)
        ensure_default_admin(
            db,
            phone=settings.admin_default_phone,
            name=settings.admin_default_name,
            password=settings.admin_default_password,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

from app.core.tz import today_beijing

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.engine.service import ScoringService
from app.models.user import User
from app.schemas.model_config import (
    ModelConfigActivateResponse,
    ModelConfigClone,
    ModelConfigCreate,
    ModelConfigListResponse,
    ModelConfigRead,
    ModelConfigUpdate,
)
from app.services import model_config as svc

router = APIRouter()


require_admin = require_roles("admin")


@router.get("", response_model=ModelConfigListResponse)
def list_model_configs(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ModelConfigListResponse:
    items = svc.list_configs(db)
    return ModelConfigListResponse(
        items=[ModelConfigRead.model_validate(it) for it in items],
        total=len(items),
    )


@router.get("/active", response_model=ModelConfigRead)
def get_active_model_config(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ModelConfigRead:
    cfg = svc.get_active(db)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active ModelConfig",
        )
    return ModelConfigRead.model_validate(cfg)


@router.get("/{config_id}", response_model=ModelConfigRead)
def get_model_config(
    config_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ModelConfigRead:
    try:
        cfg = svc.get_config(db, config_id)
    except svc.ModelConfigError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(err)
        ) from err
    return ModelConfigRead.model_validate(cfg)


@router.post(
    "",
    response_model=ModelConfigRead,
    status_code=status.HTTP_201_CREATED,
)
def create_model_config(
    payload: ModelConfigCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> ModelConfigRead:
    try:
        cfg = svc.create_config(
            db,
            name=payload.name,
            weights_json=payload.weights_json,
            thresholds_json=payload.thresholds_json,
            kelly_bands_json=payload.kelly_bands_json,
            scrape_schedule_json=payload.scrape_schedule_json,
            created_by=user.id,
        )
    except svc.ModelConfigError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
        ) from err
    return ModelConfigRead.model_validate(cfg)


@router.patch("/{config_id}", response_model=ModelConfigRead)
def update_model_config(
    config_id: int,
    payload: ModelConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ModelConfigRead:
    try:
        cfg = svc.update_config(
            db,
            config_id,
            name=payload.name,
            weights_json=payload.weights_json,
            thresholds_json=payload.thresholds_json,
            kelly_bands_json=payload.kelly_bands_json,
            scrape_schedule_json=payload.scrape_schedule_json,
        )
    except svc.ModelConfigError as err:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in str(err)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(err)) from err
    return ModelConfigRead.model_validate(cfg)


@router.post(
    "/{config_id}/clone",
    response_model=ModelConfigRead,
    status_code=status.HTTP_201_CREATED,
)
def clone_model_config(
    config_id: int,
    payload: ModelConfigClone,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> ModelConfigRead:
    try:
        cfg = svc.clone_config(db, config_id, new_name=payload.name, created_by=user.id)
    except svc.ModelConfigError as err:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in str(err)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(err)) from err
    return ModelConfigRead.model_validate(cfg)


@router.post("/{config_id}/activate", response_model=ModelConfigActivateResponse)
def activate_model_config(
    config_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ModelConfigActivateResponse:
    try:
        cfg = svc.activate_config(db, config_id)
    except svc.ModelConfigError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(err)
        ) from err

    # TD-6: activating a new ModelConfig must take effect on today's dashboard
    # without waiting for the next scoring cron. Synchronously rescore today so
    # returned payload can tell the UI how many rows changed.
    recomputed = 0
    try:
        scoring = ScoringService(db)
        today = today_beijing()
        recomputed = len(scoring.compute_for_date(today, cfg.id))
    except Exception as err:  # pragma: no cover - defensive
        # Never block activation on a rescoring failure; log-like fallback.
        # The scheduled cron will catch up later.
        import logging

        logging.getLogger(__name__).warning(
            "activate %s succeeded but same-day rescoring failed: %s",
            cfg.id,
            err,
        )

    payload = ModelConfigRead.model_validate(cfg).model_dump()
    payload["scores_recomputed"] = recomputed
    return ModelConfigActivateResponse.model_validate(payload)


__all__ = ["router"]

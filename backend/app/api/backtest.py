from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.engine.backtest_service import BacktestService
from app.models import BacktestSession, ModelConfig, SportteryMatchOdds
from app.models.user import User
from app.schemas.backtest import (
    BacktestCompareResponse,
    BacktestCreate,
    BacktestListResponse,
    BacktestSummary,
)
from app.services import model_config as mc_svc

router = APIRouter()

MAX_RANGE_DAYS = 90


def _is_admin(user: User) -> bool:
    return user.role == "admin"


def _visibility_filter(user: User):
    """Return a SQLAlchemy filter expression or None (admin = no filter)."""
    if _is_admin(user):
        return None
    return BacktestSession.user_id == user.id


def _authorize_view(session: BacktestSession, user: User) -> None:
    if _is_admin(user):
        return
    if session.user_id is None or session.user_id == user.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to view this backtest",
    )


def _authorize_delete(session: BacktestSession, user: User) -> None:
    if _is_admin(user):
        return
    if session.user_id == user.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to delete this backtest",
    )


def _summary(db: Session, session: BacktestSession) -> BacktestSummary:
    data = BacktestSummary.model_validate(session).model_dump()
    bets = data.get("bets_detail")
    if isinstance(bets, list):
        match_ids = [
            int(b["match_id"])
            for b in bets
            if isinstance(b, dict) and b.get("match_id") is not None
        ]
        odds_rows = (
            db.query(SportteryMatchOdds)
            .filter(SportteryMatchOdds.match_id.in_(match_ids))
            .all()
            if match_ids
            else []
        )
        by_match: dict[int, SportteryMatchOdds] = {}
        priority = {"titan007": 0, "sporttery": 1, "other": 2}
        for row in odds_rows:
            existing = by_match.get(row.match_id)
            if existing is None or priority.get(row.source, 99) < priority.get(existing.source, 99):
                by_match[row.match_id] = row
        for bet in bets:
            if not isinstance(bet, dict) or bet.get("handicap_value") is not None:
                continue
            match_id = bet.get("match_id")
            odds = by_match.get(int(match_id)) if match_id is not None else None
            if odds is not None and odds.handicap_value is not None:
                bet["handicap_value"] = str(odds.handicap_value)
    return BacktestSummary.model_validate(data)


def _resolve_model_config_id(db: Session, model_config_id: int | None) -> int:
    if model_config_id is not None:
        cfg = db.get(ModelConfig, model_config_id)
        if cfg is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ModelConfig not found",
            )
        return cfg.id
    cfg = mc_svc.resolve_default(db)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No ModelConfig available",
        )
    return cfg.id


@router.post(
    "",
    response_model=BacktestSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_backtest(
    payload: BacktestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BacktestSummary:
    if payload.date_from > payload.date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from must be <= date_to",
        )
    span = (payload.date_to - payload.date_from).days
    if span > MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"range too large: max {MAX_RANGE_DAYS} days",
        )

    cfg_id = _resolve_model_config_id(db, payload.model_config_id)
    svc = BacktestService(db)
    session = svc.run(
        model_config_id=cfg_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
        mode=payload.mode,
        initial_capital=payload.initial_capital,
        fixed_stake=payload.fixed_stake,
        user_id=user.id,
    )
    return _summary(db, session)


@router.get("", response_model=BacktestListResponse)
def list_backtests(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BacktestListResponse:
    visibility = _visibility_filter(user)
    base = db.query(BacktestSession)
    if visibility is not None:
        base = base.filter(visibility)
    total = base.count()
    rows = base.order_by(BacktestSession.id.desc()).offset(offset).limit(limit).all()
    items = [_summary(db, r) for r in rows]
    return BacktestListResponse(items=items, total=total)


@router.get("/compare", response_model=BacktestCompareResponse)
def compare_backtests(
    a: Annotated[int, Query(ge=1)],
    b: Annotated[int, Query(ge=1)],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BacktestCompareResponse:
    sess_a = db.get(BacktestSession, a)
    sess_b = db.get(BacktestSession, b)
    if sess_a is None or sess_b is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest session not found",
        )
    _authorize_view(sess_a, user)
    _authorize_view(sess_b, user)
    return BacktestCompareResponse(
        a=_summary(db, sess_a),
        b=_summary(db, sess_b),
    )


@router.get("/{session_id}", response_model=BacktestSummary)
def get_backtest(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BacktestSummary:
    session = db.get(BacktestSession, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest session not found",
        )
    _authorize_view(session, user)
    return _summary(db, session)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_backtest(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    session = db.get(BacktestSession, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest session not found",
        )
    _authorize_delete(session, user)
    db.delete(session)
    db.commit()


__all__ = ["router"]

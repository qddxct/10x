from __future__ import annotations

from datetime import date, datetime, timedelta

from app.core.tz import today_beijing
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import League, ModelConfig, SportteryMatch, SportteryMatchResult, SportteryMatchScore
from app.models.user import User
from app.schemas.review import ReviewItem, ReviewListResponse, ReviewUpdate

router = APIRouter()

require_admin = require_roles("admin")


def _sporttery_url(mid: str | None) -> str | None:
    if not mid:
        return None
    return f"https://www.sporttery.cn/jc/zqdz/index.html?showType=2&mid={mid}"


def _computed_handicap_result(
    match: SportteryMatch, result: SportteryMatchResult | None
) -> str | None:
    if result is None:
        return None
    if match.hhad_goal_line is None:
        return None

    adjusted_home_score = float(result.home_score) + float(match.hhad_goal_line)
    if adjusted_home_score > result.away_score:
        return "home_win"
    if adjusted_home_score < result.away_score:
        return "away_win"
    return "draw"


def _suggested_hit(
    score: SportteryMatchScore, match: SportteryMatch, result: SportteryMatchResult | None
) -> bool | None:
    """Auto-compute whether the recommendation would have hit.

    Only meaningful when the score carries a bet_type AND the match has a
    finished result. Otherwise returns None.
    """
    if result is None or score.bet_type is None:
        return None
    if score.bet_type == "draw":
        return result.home_score == result.away_score
    if score.bet_type == "handicap_draw":
        return _computed_handicap_result(match, result) == "draw"
    return None


def _to_item(
    *,
    score: SportteryMatchScore,
    match: SportteryMatch,
    result: SportteryMatchResult | None,
    league_name: str | None,
    model_name: str | None,
) -> ReviewItem:
    bet_odds = None
    if score.bet_type == "draw":
        bet_odds = match.had_d
    elif score.bet_type == "handicap_draw":
        bet_odds = match.hhad_d

    return ReviewItem(
        score_id=score.id,
        match_id=match.id,
        match_date=match.match_date,
        match_round=match.round,
        sporttery_match_id=match.sporttery_match_id,
        sporttery_url=_sporttery_url(match.sporttery_match_id),
        league_name=league_name,
        home_team=match.home_team,
        away_team=match.away_team,
        home_score=result.home_score if result is not None else None,
        away_score=result.away_score if result is not None else None,
        result=result.result if result is not None else None,
        handicap_result=_computed_handicap_result(match, result),
        total_score=score.total_score,
        bet_type=score.bet_type,
        bet_odds=bet_odds,
        kelly_pct=score.kelly_pct,
        is_recommended=score.is_recommended,
        actual_hit=score.actual_hit,
        suggested_actual_hit=_suggested_hit(score, match, result),
        bet_amount=score.bet_amount,
        notes=score.notes,
        model_config_id=score.model_config_id,
        model_name=model_name,
        user_id=score.user_id,
        updated_at=score.updated_at,
    )


@router.get("", response_model=ReviewListResponse)
def list_reviews(
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    only_recommended: Annotated[bool, Query()] = False,
    model_config_id: Annotated[int | None, Query()] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ReviewListResponse:
    """List finished matches with a computed score (eligible for review)."""
    if date_from is None:
        date_from = (today_beijing() - timedelta(days=14))
    if date_to is None:
        date_to = today_beijing()
    if date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from must be <= date_to",
        )

    start = datetime.combine(date_from, datetime.min.time())
    end = datetime.combine(date_to, datetime.min.time()) + timedelta(days=1)

    q = (
        db.query(SportteryMatchScore, SportteryMatch, SportteryMatchResult, League, ModelConfig)
        .join(SportteryMatch, SportteryMatchScore.match_id == SportteryMatch.id)
        .join(ModelConfig, SportteryMatchScore.model_config_id == ModelConfig.id)
        .outerjoin(SportteryMatchResult, SportteryMatchResult.match_id == SportteryMatch.id)
        .outerjoin(League, SportteryMatch.league_id == League.id)
        .filter(
            and_(
                SportteryMatch.match_date >= start,
                SportteryMatch.match_date < end,
                SportteryMatch.status == "finished",
            )
        )
    )
    if only_recommended:
        q = q.filter(SportteryMatchScore.is_recommended.is_(True))
    if model_config_id is not None:
        q = q.filter(SportteryMatchScore.model_config_id == model_config_id)

    rows = q.order_by(
        SportteryMatch.match_date.desc(),
        SportteryMatch.id.asc(),
        ModelConfig.is_active.desc(),
        ModelConfig.id.asc(),
    ).all()
    items = [
        _to_item(
            score=score,
            match=match,
            result=result,
            league_name=(lg.name if lg is not None else None),
            model_name=cfg.name,
        )
        for score, match, result, lg, cfg in rows
    ]
    return ReviewListResponse(items=items, total=len(items))


def _load_score_or_404(db: Session, score_id: int) -> SportteryMatchScore:
    score = db.get(SportteryMatchScore, score_id)
    if score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Score not found"
        )
    return score


@router.get("/{score_id}", response_model=ReviewItem)
def get_review(
    score_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ReviewItem:
    score = _load_score_or_404(db, score_id)
    match = db.get(SportteryMatch, score.match_id)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Match not found"
        )
    result = (
        db.query(SportteryMatchResult).filter(SportteryMatchResult.match_id == match.id).one_or_none()
    )
    lg = db.get(League, match.league_id) if match.league_id else None
    cfg = db.get(ModelConfig, score.model_config_id)
    return _to_item(
        score=score,
        match=match,
        result=result,
        league_name=lg.name if lg is not None else None,
        model_name=cfg.name if cfg is not None else None,
    )


@router.patch("/{score_id}", response_model=ReviewItem)
def patch_review(
    score_id: int,
    payload: ReviewUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ReviewItem:
    score = _load_score_or_404(db, score_id)

    data = payload.model_dump(exclude_unset=True)
    expected_updated_at = data.pop("expected_updated_at", None)
    if expected_updated_at is not None:
        current = score.updated_at
        # Compare with second precision (DB drivers/serializers often drop µs).
        if current is None or current.replace(
            microsecond=0
        ) != expected_updated_at.replace(microsecond=0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Score has been updated by another user; please reload.",
            )

    if "actual_hit" in data:
        score.actual_hit = data["actual_hit"]
    if "bet_amount" in data:
        score.bet_amount = data["bet_amount"]
    if "notes" in data:
        score.notes = data["notes"]
    db.commit()
    db.refresh(score)

    match = db.get(SportteryMatch, score.match_id)
    result = (
        db.query(SportteryMatchResult)
        .filter(SportteryMatchResult.match_id == score.match_id)
        .one_or_none()
    )
    lg = (
        db.get(League, match.league_id)
        if (match is not None and match.league_id)
        else None
    )
    cfg = db.get(ModelConfig, score.model_config_id)
    return _to_item(
        score=score,
        match=match,
        result=result,
        league_name=lg.name if lg is not None else None,
        model_name=cfg.name if cfg is not None else None,
    )


__all__ = ["router"]

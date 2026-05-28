from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.tz import now_beijing, today_beijing
from app.models import (
    ComboRecommendation,
    League,
    ModelConfig,
    SportteryMatch,
    SportteryMatchResult,
    SportteryMatchScore,
)
from app.models.user import User
from app.schemas.combo_recommendation import (
    ComboLegOut,
    ComboRecommendationListResponse,
    ComboRecommendationOut,
    ComboSnapshotResult,
)
from app.services import model_config as mc_svc

router = APIRouter()
require_admin = require_roles("admin")


def _resolve_model_config_id(db: Session, model_config_id: int | None) -> int:
    if model_config_id is not None:
        return model_config_id
    cfg = mc_svc.resolve_default(db)
    if cfg is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No ModelConfig available")
    return cfg.id


def _sporttery_url(mid: str | None) -> str | None:
    if not mid:
        return None
    return f"https://www.sporttery.cn/jc/zqdz/index.html?showType=2&mid={mid}"


def _bet_odds(score: SportteryMatchScore, match: SportteryMatch) -> Decimal | None:
    if score.bet_type == "draw":
        return match.had_d
    if score.bet_type == "handicap_draw":
        return match.hhad_d
    return None


def _handicap_result(match: SportteryMatch, result: SportteryMatchResult | None) -> str | None:
    if result is None:
        return None
    if match.hhad_goal_line is None:
        return None
    adjusted_home = float(result.home_score) + float(match.hhad_goal_line)
    if adjusted_home > result.away_score:
        return "home_win"
    if adjusted_home < result.away_score:
        return "away_win"
    return "draw"


def _leg_hit(score: SportteryMatchScore, match: SportteryMatch, result: SportteryMatchResult | None) -> bool | None:
    if result is None or score.bet_type is None:
        return None
    if score.bet_type == "draw":
        return result.home_score == result.away_score
    if score.bet_type == "handicap_draw":
        return _handicap_result(match, result) == "draw"
    return None


def _leg_snapshot(
    *, db: Session, score: SportteryMatchScore, match: SportteryMatch
) -> dict[str, Any]:
    league = db.get(League, match.league_id) if match.league_id else None
    odds = _bet_odds(score, match)
    return {
        "score_id": score.id,
        "match_id": match.id,
        "match_round": match.round,
        "match_date": match.match_date.isoformat() if match.match_date else None,
        "league_name": league.name if league is not None else None,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "bet_type": score.bet_type,
        "bet_odds": str(odds) if odds is not None else None,
        "total_score": score.total_score,
        "sporttery_url": _sporttery_url(match.sporttery_match_id),
    }


def _query_ranked_scores(db: Session, *, model_config_id: int) -> list[tuple[SportteryMatchScore, SportteryMatch]]:
    return (
        db.query(SportteryMatchScore, SportteryMatch)
        .join(SportteryMatch, SportteryMatchScore.match_id == SportteryMatch.id)
        .filter(
            and_(
                SportteryMatch.match_date >= now_beijing(),
                SportteryMatch.status.in_(("scheduled", "in_progress")),
                SportteryMatchScore.model_config_id == model_config_id,
                SportteryMatchScore.bet_type.isnot(None),
            )
        )
        .order_by(
            SportteryMatchScore.is_recommended.desc(),
            SportteryMatchScore.total_score.desc(),
            SportteryMatch.match_date.asc(),
        )
        .all()
    )


def _combo_rows(db: Session, *, model_config_id: int) -> list[dict[str, Any]]:
    ranked = _query_ranked_scores(db, model_config_id=model_config_id)
    if len(ranked) < 2:
        return []

    combos: list[tuple[int, str, list[tuple[SportteryMatchScore, SportteryMatch]]]] = [
        (1, "2串1 首选", ranked[:2]),
    ]
    if len(ranked) >= 3:
        combos.append((2, "2串1 备选", ranked[1:3]))

    rows: list[dict[str, Any]] = []
    for rank, title, legs in combos:
        odds_values = [_bet_odds(score, match) for score, match in legs]
        combo_odds = None
        if all(value is not None for value in odds_values):
            combo_odds = Decimal("1")
            for value in odds_values:
                combo_odds *= value or Decimal("0")
        rows.append(
            {
                "rank": rank,
                "title": title,
                "combo_odds": combo_odds,
                "avg_score": round(sum(score.total_score for score, _ in legs) / len(legs)),
                "legs_json": [_leg_snapshot(db=db, score=score, match=match) for score, match in legs],
            }
        )
    return rows


def _to_out(db: Session, row: ComboRecommendation) -> ComboRecommendationOut:
    cfg = db.get(ModelConfig, row.model_config_id)
    legs: list[ComboLegOut] = []
    hits: list[bool | None] = []

    for raw_leg in row.legs_json:
        score = db.get(SportteryMatchScore, int(raw_leg["score_id"]))
        match = db.get(SportteryMatch, int(raw_leg["match_id"]))
        result = (
            db.query(SportteryMatchResult)
            .filter(SportteryMatchResult.match_id == int(raw_leg["match_id"]))
            .one_or_none()
        )
        hit = _leg_hit(score, match, result) if score is not None and match is not None else None
        hits.append(hit)
        legs.append(
            ComboLegOut(
                **raw_leg,
                home_score=result.home_score if result is not None else None,
                away_score=result.away_score if result is not None else None,
                result=result.result if result is not None else None,
                handicap_result=_handicap_result(match, result) if match is not None else None,
                hit=hit,
            )
        )

    combo_hit = None if any(hit is None for hit in hits) else all(hits)
    status = "pending" if combo_hit is None else "won" if combo_hit else "lost"
    return ComboRecommendationOut(
        id=row.id,
        recommendation_date=row.recommendation_date,
        model_config_id=row.model_config_id,
        model_name=cfg.name if cfg is not None else None,
        rank=row.rank,
        title=row.title,
        combo_odds=row.combo_odds,
        avg_score=row.avg_score,
        status=status,
        hit=combo_hit,
        created_at=row.created_at,
        legs=legs,
    )


def snapshot_today_combos(db: Session, *, model_config_id: int) -> list[ComboRecommendation]:
    today = today_beijing()
    rows = _combo_rows(db, model_config_id=model_config_id)
    saved: list[ComboRecommendation] = []
    for payload in rows:
        row = (
            db.query(ComboRecommendation)
            .filter(
                and_(
                    ComboRecommendation.recommendation_date == today,
                    ComboRecommendation.model_config_id == model_config_id,
                    ComboRecommendation.rank == payload["rank"],
                )
            )
            .one_or_none()
        )
        if row is None:
            row = ComboRecommendation(
                recommendation_date=today,
                model_config_id=model_config_id,
                **payload,
            )
            db.add(row)
        else:
            row.title = payload["title"]
            row.combo_odds = payload["combo_odds"]
            row.avg_score = payload["avg_score"]
            row.legs_json = payload["legs_json"]
        saved.append(row)
    db.commit()
    for row in saved:
        db.refresh(row)
    return saved


@router.post("/snapshot-today", response_model=ComboSnapshotResult)
def snapshot_today(
    model_config_id: Annotated[int | None, Query()] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ComboSnapshotResult:
    cfg_id = _resolve_model_config_id(db, model_config_id)
    rows = snapshot_today_combos(db, model_config_id=cfg_id)
    return ComboSnapshotResult(
        model_config_id=cfg_id,
        recommendation_date=today_beijing(),
        created=len(rows),
        items=[_to_out(db, row) for row in rows],
    )


@router.get("/history", response_model=ComboRecommendationListResponse)
def list_history(
    model_config_id: Annotated[int | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ComboRecommendationListResponse:
    q = db.query(ComboRecommendation)
    if model_config_id is not None:
        q = q.filter(ComboRecommendation.model_config_id == model_config_id)
    rows = (
        q.order_by(
            ComboRecommendation.recommendation_date.desc(),
            ComboRecommendation.rank.asc(),
            ComboRecommendation.id.desc(),
        )
        .limit(limit)
        .all()
    )
    items = [_to_out(db, row) for row in rows]
    return ComboRecommendationListResponse(items=items, total=len(items))

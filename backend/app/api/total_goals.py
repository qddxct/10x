from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.tz import now_beijing, today_beijing
from app.engine.total_goals import MODEL_VERSION, TotalGoalService
from app.models import League, SportteryMatch, SportteryMatchResult, TotalGoalRecommendation
from app.models.user import User
from app.schemas.total_goals import (
    TotalGoalCombo,
    TotalGoalComputeResult,
    TotalGoalComputeUpcomingResult,
    TotalGoalListResponse,
    TotalGoalOut,
    TotalGoalTodayResponse,
)

router = APIRouter()
require_admin = require_roles("admin")


def _sporttery_url(mid: str | None) -> str | None:
    if not mid:
        return None
    return f"https://www.sporttery.cn/jc/zqdz/index.html?showType=2&mid={mid}"


def _target_label(target: int) -> str:
    return "7+" if target == 7 else str(target)


def _target_goals(row: TotalGoalRecommendation) -> list[int]:
    data = row.explanation_json if isinstance(row.explanation_json, dict) else {}
    targets = data.get("target_goals")
    if isinstance(targets, list):
        out = [int(v) for v in targets if isinstance(v, int | float) or str(v).isdigit()]
        if out:
            return out
    return [row.target_goals]


def _target_label_for_row(row: TotalGoalRecommendation) -> str:
    data = row.explanation_json if isinstance(row.explanation_json, dict) else {}
    label = data.get("target_label")
    if isinstance(label, str) and label:
        return label
    return _target_label(row.target_goals)


def _odds_label(row: TotalGoalRecommendation) -> str | None:
    data = row.explanation_json if isinstance(row.explanation_json, dict) else {}
    odds = data.get("target_odds")
    if not isinstance(odds, dict) or not odds:
        return str(row.bet_odds) if row.bet_odds is not None else None
    parts = []
    for key in sorted(odds, key=lambda x: 7 if x == "7+" else int(x)):
        parts.append(f"{key}球 {odds[key]}")
    return " / ".join(parts)


def _attach_meta(db: Session, row: TotalGoalRecommendation) -> TotalGoalOut:
    match = db.get(SportteryMatch, row.match_id)
    result = (
        db.query(SportteryMatchResult)
        .filter(SportteryMatchResult.match_id == row.match_id)
        .one_or_none()
    )
    league_name = None
    if match is not None and match.league_id is not None:
        league = db.get(League, match.league_id)
        league_name = league.name if league is not None else None

    actual_total = None
    hit = None
    if result is not None:
        actual_total = result.home_score + result.away_score
        targets = _target_goals(row)
        hit = actual_total in targets or (7 in targets and actual_total >= 7)

    return TotalGoalOut(
        id=row.id,
        match_id=row.match_id,
        model_version=row.model_version,
        target_goals=row.target_goals,
        target_label=_target_label_for_row(row),
        odds_label=_odds_label(row),
        total_score=row.total_score,
        confidence_pct=row.confidence_pct,
        bet_odds=row.bet_odds,
        is_recommended=row.is_recommended,
        hit=hit,
        explanation=row.explanation_json,
        match_date=match.match_date if match is not None else None,
        home_team=match.home_team if match is not None else None,
        away_team=match.away_team if match is not None else None,
        league_name=league_name,
        match_round=match.round if match is not None else None,
        sporttery_url=_sporttery_url(match.sporttery_match_id if match is not None else None),
        home_score=result.home_score if result is not None else None,
        away_score=result.away_score if result is not None else None,
        actual_total_goals=actual_total,
    )


def _query_for_range(db: Session, *, start: datetime, end: datetime) -> list[TotalGoalRecommendation]:
    return (
        db.query(TotalGoalRecommendation)
        .join(SportteryMatch, TotalGoalRecommendation.match_id == SportteryMatch.id)
        .filter(
            and_(
                SportteryMatch.match_date >= start,
                SportteryMatch.match_date < end,
                TotalGoalRecommendation.model_version == MODEL_VERSION,
            )
        )
        .order_by(
            TotalGoalRecommendation.is_recommended.desc(),
            TotalGoalRecommendation.total_score.desc(),
            SportteryMatch.match_date.asc(),
        )
        .all()
    )


def _query_upcoming(db: Session, *, now: datetime) -> list[TotalGoalRecommendation]:
    return (
        db.query(TotalGoalRecommendation)
        .join(SportteryMatch, TotalGoalRecommendation.match_id == SportteryMatch.id)
        .filter(
            and_(
                SportteryMatch.match_date >= now,
                SportteryMatch.status.in_(("scheduled", "in_progress")),
                TotalGoalRecommendation.model_version == MODEL_VERSION,
            )
        )
        .order_by(
            TotalGoalRecommendation.is_recommended.desc(),
            TotalGoalRecommendation.total_score.desc(),
            SportteryMatch.match_date.asc(),
        )
        .all()
    )


def _build_combos(items: list[TotalGoalOut]) -> list[TotalGoalCombo]:
    ranked = [item for item in items if item.is_recommended]
    if len(ranked) < 2:
        ranked = items[:2]
    if len(ranked) < 2:
        return []

    legs = ranked[:2]
    odds_values = [leg.bet_odds for leg in legs]
    combo_odds = None
    if all(v is not None and v > 0 for v in odds_values):
        product = Decimal("1")
        for value in odds_values:
            product *= Decimal(value)
        combo_odds = product.quantize(Decimal("0.001"))

    if any(leg.hit is False for leg in legs):
        status = "lost"
        hit = False
    elif all(leg.hit is True for leg in legs):
        status = "won"
        hit = True
    else:
        status = "pending"
        hit = None

    return [
        TotalGoalCombo(
            title="总进球数 2串1",
            items=legs,
            combo_odds=combo_odds,
            avg_score=round(sum(leg.total_score for leg in legs) / len(legs)),
            status=status,
            hit=hit,
        )
    ]


@router.get("/today", response_model=TotalGoalTodayResponse)
def list_today_total_goals(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> TotalGoalTodayResponse:
    rows = _query_upcoming(db, now=now_beijing())
    items = [_attach_meta(db, row) for row in rows]
    return TotalGoalTodayResponse(items=items, total=len(items), combos=_build_combos(items))


@router.get("/by-date", response_model=TotalGoalListResponse)
def list_total_goals_by_date(
    target: Annotated[date, Query(alias="date")],
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> TotalGoalListResponse:
    start = datetime.combine(target, datetime.min.time())
    end = start + timedelta(days=1)
    rows = _query_for_range(db, start=start, end=end)
    items = [_attach_meta(db, row) for row in rows]
    return TotalGoalListResponse(items=items, total=len(items))


@router.post("/compute", response_model=TotalGoalComputeResult, status_code=status.HTTP_200_OK)
def compute_total_goals(
    target: Annotated[date | None, Query(alias="date")] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
) -> TotalGoalComputeResult:
    target = target or today_beijing()
    start = datetime.combine(target, datetime.min.time())
    end = start + timedelta(days=1)
    total_matches = (
        db.query(SportteryMatch)
        .filter(and_(SportteryMatch.match_date >= start, SportteryMatch.match_date < end))
        .count()
    )
    rows = TotalGoalService(db).compute_for_date(target)
    return TotalGoalComputeResult(date=target, computed=len(rows), skipped=max(0, total_matches - len(rows)))


@router.post("/compute-upcoming", response_model=TotalGoalComputeUpcomingResult, status_code=status.HTTP_200_OK)
def compute_upcoming_total_goals(
    days: Annotated[int, Query(ge=1, le=14)] = 7,
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
) -> TotalGoalComputeUpcomingResult:
    now = now_beijing()
    until = now + timedelta(days=days)
    dates = [
        row[0]
        for row in (
            db.query(SportteryMatch.match_date)
            .filter(
                and_(
                    SportteryMatch.match_date >= now,
                    SportteryMatch.match_date < until,
                    SportteryMatch.status.in_(("scheduled", "in_progress")),
                )
            )
            .order_by(SportteryMatch.match_date.asc())
            .all()
        )
    ]
    target_dates = sorted({dt.date() for dt in dates})
    svc = TotalGoalService(db)
    computed = 0
    for target in target_dates:
        computed += len(svc.compute_for_date(target))

    total_matches = (
        db.query(SportteryMatch)
        .filter(
            and_(
                SportteryMatch.match_date >= now,
                SportteryMatch.match_date < until,
                SportteryMatch.status.in_(("scheduled", "in_progress")),
            )
        )
        .count()
    )
    return TotalGoalComputeUpcomingResult(dates=target_dates, computed=computed, skipped=max(0, total_matches - computed))

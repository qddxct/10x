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
from app.models import (
    League,
    SportteryMatch,
    SportteryMatchResult,
    TotalGoalComboRecommendation,
    TotalGoalRecommendation,
)
from app.models.user import User
from app.schemas.total_goals import (
    TotalGoalCombo,
    TotalGoalComboHistoryItem,
    TotalGoalComboHistoryResponse,
    TotalGoalComboSnapshotResult,
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


def _item_target_odds(item: TotalGoalOut) -> list[Decimal]:
    odds = item.explanation.get("target_odds") if isinstance(item.explanation, dict) else None
    if isinstance(odds, dict) and odds:
        values: list[Decimal] = []
        for value in odds.values():
            try:
                values.append(Decimal(str(value)))
            except Exception:
                continue
        if values:
            return values
    return [Decimal(item.bet_odds)] if item.bet_odds is not None else []


def _combo_odds_range(legs: list[TotalGoalOut]) -> tuple[Decimal | None, str | None]:
    odds_groups = [_item_target_odds(leg) for leg in legs]
    if not odds_groups or any(not group for group in odds_groups):
        return None, None

    products = [Decimal("1")]
    for group in odds_groups:
        products = [base * odd for base in products for odd in group]
    if not products:
        return None, None

    stake_split = Decimal(str(len(products)))
    low = (min(products) / stake_split).quantize(Decimal("0.001"))
    high = (max(products) / stake_split).quantize(Decimal("0.001"))
    if low == high:
        return low, str(low)
    return low, f"{low} - {high}"


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
    combo_odds, combo_odds_label = _combo_odds_range(legs)

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
            combo_odds_label=combo_odds_label,
            avg_score=round(sum(leg.total_score for leg in legs) / len(legs)),
            status=status,
            hit=hit,
        )
    ]


def _combo_leg_snapshot(item: TotalGoalOut) -> dict:
    return {
        "id": item.id,
        "match_id": item.match_id,
        "model_version": item.model_version,
        "target_goals": item.target_goals,
        "target_label": item.target_label,
        "odds_label": item.odds_label,
        "total_score": item.total_score,
        "confidence_pct": str(item.confidence_pct) if item.confidence_pct is not None else None,
        "bet_odds": str(item.bet_odds) if item.bet_odds is not None else None,
        "is_recommended": item.is_recommended,
        "explanation": item.explanation,
        "match_date": item.match_date.isoformat() if item.match_date is not None else None,
        "home_team": item.home_team,
        "away_team": item.away_team,
        "league_name": item.league_name,
        "match_round": item.match_round,
        "sporttery_url": item.sporttery_url,
    }


def _combo_history_to_out(db: Session, row: TotalGoalComboRecommendation) -> TotalGoalComboHistoryItem:
    legs: list[TotalGoalOut] = []
    for raw in row.legs_json:
        match_id = int(raw["match_id"])
        result = (
            db.query(SportteryMatchResult)
            .filter(SportteryMatchResult.match_id == match_id)
            .one_or_none()
        )
        actual_total = None
        hit = None
        if result is not None:
            actual_total = result.home_score + result.away_score
            targets = raw.get("explanation", {}).get("target_goals") if isinstance(raw.get("explanation"), dict) else None
            if not isinstance(targets, list):
                targets = [raw.get("target_goals")]
            targets = [int(v) for v in targets if v is not None]
            hit = actual_total in targets or (7 in targets and actual_total >= 7)

        legs.append(
            TotalGoalOut(
                id=int(raw["id"]),
                match_id=match_id,
                model_version=str(raw.get("model_version") or MODEL_VERSION),
                target_goals=int(raw.get("target_goals") or 0),
                target_label=str(raw.get("target_label") or raw.get("target_goals") or "-"),
                odds_label=raw.get("odds_label"),
                total_score=int(raw.get("total_score") or 0),
                confidence_pct=Decimal(str(raw["confidence_pct"])) if raw.get("confidence_pct") is not None else None,
                bet_odds=Decimal(str(raw["bet_odds"])) if raw.get("bet_odds") is not None else None,
                is_recommended=bool(raw.get("is_recommended")),
                hit=hit,
                explanation=raw.get("explanation"),
                match_date=raw.get("match_date"),
                home_team=raw.get("home_team"),
                away_team=raw.get("away_team"),
                league_name=raw.get("league_name"),
                match_round=raw.get("match_round"),
                sporttery_url=raw.get("sporttery_url"),
                home_score=result.home_score if result is not None else None,
                away_score=result.away_score if result is not None else None,
                actual_total_goals=actual_total,
            )
        )

    if any(leg.hit is False for leg in legs):
        status = "lost"
        hit = False
    elif legs and all(leg.hit is True for leg in legs):
        status = "won"
        hit = True
    else:
        status = "pending"
        hit = None

    combo_odds, combo_odds_label = _combo_odds_range(legs)

    return TotalGoalComboHistoryItem(
        id=row.id,
        recommendation_date=row.recommendation_date,
        model_version=row.model_version,
        created_at=row.created_at,
        title=row.title,
        items=legs,
        combo_odds=combo_odds,
        combo_odds_label=combo_odds_label,
        avg_score=row.avg_score,
        status=status,
        hit=hit,
    )


def snapshot_today_total_goal_combos(db: Session) -> list[TotalGoalComboRecommendation]:
    rows = _query_upcoming(db, now=now_beijing())
    items = [_attach_meta(db, row) for row in rows]
    combos = _build_combos(items)
    today = today_beijing()
    saved: list[TotalGoalComboRecommendation] = []
    for idx, combo in enumerate(combos, start=1):
        row = (
            db.query(TotalGoalComboRecommendation)
            .filter(
                and_(
                    TotalGoalComboRecommendation.recommendation_date == today,
                    TotalGoalComboRecommendation.rank == idx,
                    TotalGoalComboRecommendation.model_version == MODEL_VERSION,
                )
            )
            .one_or_none()
        )
        payload = {
            "title": combo.title,
            "combo_odds": combo.combo_odds,
            "combo_odds_label": combo.combo_odds_label,
            "avg_score": combo.avg_score,
            "legs_json": [_combo_leg_snapshot(item) for item in combo.items],
        }
        if row is None:
            row = TotalGoalComboRecommendation(
                recommendation_date=today,
                rank=idx,
                model_version=MODEL_VERSION,
                **payload,
            )
            db.add(row)
        else:
            row.title = payload["title"]
            row.combo_odds = payload["combo_odds"]
            row.combo_odds_label = payload["combo_odds_label"]
            row.avg_score = payload["avg_score"]
            row.legs_json = payload["legs_json"]
        saved.append(row)
    db.commit()
    for row in saved:
        db.refresh(row)
    return saved


@router.get("/today", response_model=TotalGoalTodayResponse)
def list_today_total_goals(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> TotalGoalTodayResponse:
    rows = _query_upcoming(db, now=now_beijing())
    items = [_attach_meta(db, row) for row in rows]
    return TotalGoalTodayResponse(items=items, total=len(items), combos=_build_combos(items))


@router.post("/snapshot-today", response_model=TotalGoalComboSnapshotResult)
def snapshot_today_total_goals(
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
) -> TotalGoalComboSnapshotResult:
    rows = snapshot_today_total_goal_combos(db)
    return TotalGoalComboSnapshotResult(
        recommendation_date=today_beijing(),
        created=len(rows),
        items=[_combo_history_to_out(db, row) for row in rows],
    )


@router.get("/history", response_model=TotalGoalComboHistoryResponse)
def list_total_goal_history(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> TotalGoalComboHistoryResponse:
    rows = (
        db.query(TotalGoalComboRecommendation)
        .filter(TotalGoalComboRecommendation.model_version == MODEL_VERSION)
        .order_by(
            TotalGoalComboRecommendation.recommendation_date.desc(),
            TotalGoalComboRecommendation.rank.asc(),
            TotalGoalComboRecommendation.id.desc(),
        )
        .limit(limit)
        .all()
    )
    items = [_combo_history_to_out(db, row) for row in rows]
    return TotalGoalComboHistoryResponse(items=items, total=len(items))


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

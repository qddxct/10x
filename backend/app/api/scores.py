from __future__ import annotations

from datetime import date, datetime, timedelta

from app.core.tz import now_beijing, today_beijing
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.engine.service import ScoringService
from app.models import (
    League,
    ModelConfig,
    SportteryMatch,
    SportteryMatchOdds,
    SportteryMatchScore,
    SportteryMatchTeamStats,
)
from app.models.user import User
from app.schemas.scores import (
    ScoreBreakdown,
    ScoreBreakdownItem,
    ScoreComputeResult,
    ScoreComputeUpcomingResult,
    ScoreListResponse,
    ScoreOut,
    ScoreUpdate,
)
from app.services import model_config as mc_svc

router = APIRouter()

require_admin = require_roles("admin")

_DIMENSION_EXPLANATIONS: dict[str, str] = {
    "euro_score": "欧赔三项离散度与甜区（胜/负 2.30-2.80，平 3.00-3.40）",  # noqa: RUF001
    "asian_score": "亚盘深度：平手 20、平半 15、半球 5",  # noqa: RUF001
    "goals_score": "总进球线：≤2.25 球 20，2.5 球 10，≥2.75 球 0",  # noqa: RUF001
    "intent_score": "战意：杯赛/淘汰赛 15，其他 5",  # noqa: RUF001
    "compression_score": "平赔压缩度：≤3.2 赔 20，<3.6 赔 10，否则 0",  # noqa: RUF001
    "team_stats_score": "球队状态：排名接近度 + 近期状态 + 联赛平局率",  # noqa: RUF001
}

_DIMENSION_MAX_SCORES: dict[str, int] = {
    "euro_score": 25,
    "asian_score": 20,
    "goals_score": 20,
    "intent_score": 15,
    "compression_score": 20,
    "team_stats_score": 20,
}

_RULE_EXPLANATIONS: dict[str, str] = {
    "DRAW_V32_CORE": (
        "V3.2 平局核心规则：命中后固定规则分 108，Kelly 1.00%。"
        "触发条件是交锋平局或一球差特征、近期小比分倾向、浅盘口，并且平赔不低于 3.10。"
    ),
    "HDRAW_V32_CORE": (
        "V3.2 让平核心规则：命中后固定规则分 116，Kelly 1.50%。"
        "触发条件是一球/一球球半盘口、排名差 6-15、让平赔不低于 3.50，"
        "并且赛季和主客场平局属性不低。"
    ),
}


def _sporttery_url(mid: str | None) -> str | None:
    if not mid:
        return None
    return f"https://www.sporttery.cn/jc/zqdz/index.html?showType=2&mid={mid}"


def _dimension_total(score: SportteryMatchScore) -> int:
    return sum(getattr(score, name) for name in _DIMENSION_MAX_SCORES)


def _rule_name_for_score(score: SportteryMatchScore) -> str | None:
    if score.bet_type == "draw" and score.total_score == 108:
        return "DRAW_V32_CORE"
    if score.bet_type == "handicap_draw" and score.total_score == 116:
        return "HDRAW_V32_CORE"
    return None


def _is_v32_rule_model(db: Session, score: SportteryMatchScore) -> bool:
    cfg = db.get(ModelConfig, score.model_config_id)
    thresholds = cfg.thresholds_json if cfg is not None else None
    return isinstance(thresholds, dict) and thresholds.get("strategy") == "empirical_v32_filtered"


def _attach_match_meta(db: Session, score: SportteryMatchScore) -> ScoreOut:
    match = db.get(SportteryMatch, score.match_id)
    league_name = None
    match_date = None
    home = None
    away = None
    match_round = None
    sporttery_match_id = None
    had_draw_odds = None
    hhad_draw_odds = None
    if match is not None:
        match_date = match.match_date
        home = match.home_team
        away = match.away_team
        match_round = match.round
        sporttery_match_id = match.sporttery_match_id
        had_draw_odds = match.had_d
        hhad_draw_odds = match.hhad_d
        if match.league_id:
            lg = db.get(League, match.league_id)
            if lg is not None:
                league_name = lg.name

    odds = (
        db.query(SportteryMatchOdds)
        .filter(
            and_(
                SportteryMatchOdds.match_id == score.match_id,
                SportteryMatchOdds.source == "sporttery",
            )
        )
        .order_by(SportteryMatchOdds.scraped_at.desc())
        .first()
    )
    if odds is not None:
        had_draw_odds = had_draw_odds or odds.draw_odds
        hhad_draw_odds = hhad_draw_odds or odds.draw_handicap_odds

    out = ScoreOut.model_validate(score)
    out.match_date = match_date
    out.home_team = home
    out.away_team = away
    out.league_name = league_name
    out.match_round = match_round
    out.sporttery_match_id = sporttery_match_id
    out.sporttery_url = _sporttery_url(sporttery_match_id)
    out.had_draw_odds = had_draw_odds
    out.hhad_draw_odds = hhad_draw_odds
    if score.bet_type == "draw":
        out.bet_odds = had_draw_odds
    elif score.bet_type == "handicap_draw":
        out.bet_odds = hhad_draw_odds

    diagnostic_score = _dimension_total(score)
    rule_name = _rule_name_for_score(score) if _is_v32_rule_model(db, score) else None
    out.diagnostic_score = diagnostic_score
    if rule_name is not None and score.is_recommended:
        out.score_mode = "rule"
        out.rule_name = rule_name
        out.rule_score = score.total_score
        out.rule_explanation = _RULE_EXPLANATIONS.get(rule_name)
    else:
        out.score_mode = "diagnostic"
    return out


def _query_scores_for_range(
    db: Session, *, start: datetime, end: datetime, model_config_id: int
) -> list[SportteryMatchScore]:
    return (
        db.query(SportteryMatchScore)
        .join(SportteryMatch, SportteryMatchScore.match_id == SportteryMatch.id)
        .filter(
            and_(
                SportteryMatch.match_date >= start,
                SportteryMatch.match_date < end,
                SportteryMatchScore.model_config_id == model_config_id,
            )
        )
        .order_by(SportteryMatchScore.total_score.desc(), SportteryMatch.match_date.asc())
        .all()
    )


def _query_upcoming_scores(
    db: Session, *, model_config_id: int, now: datetime
) -> list[SportteryMatchScore]:
    return (
        db.query(SportteryMatchScore)
        .join(SportteryMatch, SportteryMatchScore.match_id == SportteryMatch.id)
        .filter(
            and_(
                SportteryMatch.match_date >= now,
                SportteryMatch.status.in_(("scheduled", "in_progress")),
                SportteryMatchScore.model_config_id == model_config_id,
            )
        )
        .order_by(
            SportteryMatchScore.is_recommended.desc(),
            SportteryMatchScore.total_score.desc(),
            SportteryMatch.match_date.asc(),
        )
        .all()
    )


def _resolve_model_config_id(db: Session, model_config_id: int | None) -> int:
    if model_config_id is not None:
        return model_config_id
    cfg = mc_svc.resolve_default(db)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No ModelConfig available",
        )
    return cfg.id


@router.get("/today", response_model=ScoreListResponse)
def list_today_scores(
    model_config_id: Annotated[int | None, Query()] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ScoreListResponse:
    cfg_id = _resolve_model_config_id(db, model_config_id)
    rows = _query_upcoming_scores(db, model_config_id=cfg_id, now=now_beijing())
    items = [_attach_match_meta(db, r) for r in rows]
    return ScoreListResponse(items=items, total=len(items))


@router.get("/by-date", response_model=ScoreListResponse)
def list_scores_by_date(
    target: Annotated[date, Query(alias="date")],
    model_config_id: Annotated[int | None, Query()] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ScoreListResponse:
    cfg_id = _resolve_model_config_id(db, model_config_id)
    start = datetime.combine(target, datetime.min.time())
    end = start + timedelta(days=1)
    rows = _query_scores_for_range(db, start=start, end=end, model_config_id=cfg_id)
    items = [_attach_match_meta(db, r) for r in rows]
    return ScoreListResponse(items=items, total=len(items))


@router.post(
    "/compute",
    response_model=ScoreComputeResult,
    status_code=status.HTTP_200_OK,
)
def compute_scores(
    target: Annotated[date | None, Query(alias="date")] = None,
    model_config_id: Annotated[int | None, Query()] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ScoreComputeResult:
    cfg_id = _resolve_model_config_id(db, model_config_id)
    target = target or today_beijing()

    start = datetime.combine(target, datetime.min.time())
    end = start + timedelta(days=1)
    total_matches = (
        db.query(SportteryMatch)
        .filter(and_(SportteryMatch.match_date >= start, SportteryMatch.match_date < end))
        .count()
    )

    svc = ScoringService(db)
    results = svc.compute_for_date(target, cfg_id)
    return ScoreComputeResult(
        date=target,
        model_config_id=cfg_id,
        computed=len(results),
        skipped=max(0, total_matches - len(results)),
    )


@router.post(
    "/compute-upcoming",
    response_model=ScoreComputeUpcomingResult,
    status_code=status.HTTP_200_OK,
)
def compute_upcoming_scores(
    model_config_id: Annotated[int | None, Query()] = None,
    days: Annotated[int, Query(ge=1, le=14)] = 7,
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ScoreComputeUpcomingResult:
    cfg_id = _resolve_model_config_id(db, model_config_id)
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

    svc = ScoringService(db)
    computed = 0
    for target in target_dates:
        computed += len(svc.compute_for_date(target, cfg_id))

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
    return ScoreComputeUpcomingResult(
        model_config_id=cfg_id,
        dates=target_dates,
        computed=computed,
        skipped=max(0, total_matches - computed),
    )


@router.get("/{score_id}/breakdown", response_model=ScoreBreakdown)
def get_breakdown(
    score_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ScoreBreakdown:
    score = db.get(SportteryMatchScore, score_id)
    if score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Score not found"
        )
    out = _attach_match_meta(db, score)
    parts = [
        ScoreBreakdownItem(
            dimension=name,
            score=getattr(score, name),
            max_score=_DIMENSION_MAX_SCORES[name],
            explanation=_DIMENSION_EXPLANATIONS[name],
        )
        for name in (
            "euro_score",
            "asian_score",
            "goals_score",
            "intent_score",
            "compression_score",
            "team_stats_score",
        )
    ]
    return ScoreBreakdown(score=out, parts=parts)


@router.put("/{score_id}", response_model=ScoreOut)
def update_score(
    score_id: int,
    payload: ScoreUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ScoreOut:
    score = db.get(SportteryMatchScore, score_id)
    if score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Score not found"
        )
    if payload.notes is not None:
        score.notes = payload.notes
    if payload.bet_amount is not None:
        score.bet_amount = payload.bet_amount
    if payload.actual_hit is not None:
        score.actual_hit = payload.actual_hit
    db.commit()
    db.refresh(score)
    return _attach_match_meta(db, score)


__all__ = ["router", "SportteryMatchOdds", "SportteryMatchTeamStats"]

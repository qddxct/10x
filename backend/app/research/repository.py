from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session, joinedload

from app.engine.service import _pick_odds
from app.models import (
    League,
    ModelConfig,
    ModelResearchArtifact,
    ModelResearchRun,
    SportteryMatch,
    SportteryMatchScore,
)
from app.research.types import ResearchCandidate
from app.scripts.v31_combination_candidate_backtest import enrich_features

V33_RUN_NAME = "v33-single-factor-combo-diagnostic"


def date_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    return datetime.combine(start, time.min), datetime.combine(end + timedelta(days=1), time.min)


def get_model_config_id(db: Session, model_name: str) -> int:
    cfg = db.query(ModelConfig).filter(ModelConfig.name == model_name).one()
    return cfg.id


def _stats_features(match: SportteryMatch, abs_hcap: float | None) -> dict[str, Any]:
    stats = match.team_stats
    raw: dict[str, Any] = {"abs_hcap": abs_hcap}
    fields = [
        "home_rank",
        "away_rank",
        "home_season_wins",
        "home_season_draws",
        "home_season_losses",
        "away_season_wins",
        "away_season_draws",
        "away_season_losses",
        "home_home_wins",
        "home_home_draws",
        "home_home_losses",
        "away_away_wins",
        "away_away_draws",
        "away_away_losses",
        "home_recent_form",
        "away_recent_form",
        "h2h_home_wins",
        "h2h_draws",
        "h2h_away_wins",
        "h2h_matches_count",
        "h2h_one_goal_margin_count",
        "home_recent_matches_count",
        "away_recent_matches_count",
        "home_recent_low_scoring_count",
        "away_recent_low_scoring_count",
        "home_recent_goal_diff",
        "away_recent_goal_diff",
        "home_recent_win_by_1",
        "away_recent_loss_by_1",
        "away_recent_loss_by_2plus",
        "away_recent_goals_against",
    ]
    for field in fields:
        raw[field] = getattr(stats, field, None) if stats is not None else None
    return enrich_features(raw)


def _candidate_from_match(
    match: SportteryMatch,
    *,
    bet_type: str,
    total_score: int,
) -> ResearchCandidate | None:
    if match.result is None:
        return None
    odds = _pick_odds(match.odds)
    if odds is None:
        return None
    price_raw = (
        (match.had_d or odds.draw_odds)
        if bet_type == "draw"
        else (match.hhad_d or odds.draw_handicap_odds)
    )
    if price_raw is None:
        return None
    price = float(price_raw)
    if price <= 0:
        return None
    abs_hcap = abs(float(odds.handicap_value)) if odds.handicap_value is not None else None
    features = _stats_features(match, abs_hcap)
    hit = (
        match.result.result == "draw"
        if bet_type == "draw"
        else match.result.handicap_result == "draw"
    )
    score_label = f"{match.result.home_score}-{match.result.away_score}"
    result_label = f"{score_label} {'命中' if hit else '未命中'}"
    return ResearchCandidate(
        match_id=match.id,
        match_date=match.match_date.date(),
        league=match.league.name,
        home_team=match.home_team,
        away_team=match.away_team,
        bet_type=bet_type,  # type: ignore[arg-type]
        odds=price,
        is_hit=hit,
        total_score=total_score,
        handicap_value=float(odds.handicap_value) if odds.handicap_value is not None else None,
        had_d=float(odds.draw_odds) if odds.draw_odds is not None else None,
        hhad_d=float(odds.draw_handicap_odds) if odds.draw_handicap_odds is not None else None,
        abs_hcap=features.get("abs_hcap"),
        rank_gap=features.get("rank_gap"),
        recent_draw_sum=features.get("recent_draw_sum"),
        recent_low_scoring_sum=features.get("recent_low_scoring_sum"),
        h2h_draw_rate=features.get("h2h_draw_rate"),
        h2h_one_goal_margin_rate=features.get("h2h_one_goal_margin_rate"),
        home_recent_goal_diff=features.get("home_recent_goal_diff"),
        away_recent_goal_diff=features.get("away_recent_goal_diff"),
        result_label=result_label,
    )


def _base_match_query(db: Session, start: date, end: date):
    start_dt, end_dt = date_bounds(start, end)
    return (
        db.query(SportteryMatch)
        .join(League, SportteryMatch.league_id == League.id)
        .options(joinedload(SportteryMatch.league))
        .options(joinedload(SportteryMatch.result))
        .options(joinedload(SportteryMatch.team_stats))
        .options(joinedload(SportteryMatch.odds))
        .filter(SportteryMatch.match_date >= start_dt)
        .filter(SportteryMatch.match_date < end_dt)
        .filter(SportteryMatch.status == "finished")
    )


def load_model_candidates(
    db: Session, *, model_config_id: int, start: date, end: date
) -> list[ResearchCandidate]:
    start_dt, end_dt = date_bounds(start, end)
    rows = (
        db.query(SportteryMatchScore)
        .join(SportteryMatch, SportteryMatchScore.match_id == SportteryMatch.id)
        .options(joinedload(SportteryMatchScore.match).joinedload(SportteryMatch.league))
        .options(joinedload(SportteryMatchScore.match).joinedload(SportteryMatch.result))
        .options(joinedload(SportteryMatchScore.match).joinedload(SportteryMatch.team_stats))
        .options(joinedload(SportteryMatchScore.match).joinedload(SportteryMatch.odds))
        .filter(SportteryMatchScore.model_config_id == model_config_id)
        .filter(SportteryMatchScore.is_recommended.is_(True))
        .filter(SportteryMatch.match_date >= start_dt)
        .filter(SportteryMatch.match_date < end_dt)
        .order_by(SportteryMatch.match_date.asc(), SportteryMatch.id.asc())
        .all()
    )
    out: list[ResearchCandidate] = []
    for score in rows:
        if score.bet_type not in {"draw", "handicap_draw"}:
            continue
        candidate = _candidate_from_match(
            score.match, bet_type=score.bet_type, total_score=score.total_score
        )
        if candidate is not None:
            out.append(candidate)
    return out


def load_market_candidates(db: Session, *, start: date, end: date) -> list[ResearchCandidate]:
    out: list[ResearchCandidate] = []
    for match in (
        _base_match_query(db, start, end)
        .order_by(SportteryMatch.match_date.asc(), SportteryMatch.id.asc())
        .all()
    ):
        draw = _candidate_from_match(match, bet_type="draw", total_score=0)
        hdraw = _candidate_from_match(match, bet_type="handicap_draw", total_score=0)
        if draw is not None:
            out.append(draw)
        if hdraw is not None:
            out.append(hdraw)
    return out


def replace_existing_run(db: Session, *, name: str) -> None:
    ids = [
        row.id for row in db.query(ModelResearchRun.id).filter(ModelResearchRun.name == name).all()
    ]
    if ids:
        db.execute(delete(ModelResearchRun).where(ModelResearchRun.id.in_(ids)))
        db.commit()


def save_research_run(
    db: Session,
    *,
    name: str,
    base_model_config_id: int,
    start: date,
    end: date,
    random_seed: int,
    random_trials: int,
    summary: dict[str, Any],
    report_path: str,
    artifacts: list[tuple[str, str, dict[str, Any]]],
) -> ModelResearchRun:
    run = ModelResearchRun(
        name=name,
        base_model_config_id=base_model_config_id,
        date_from=start,
        date_to=end,
        random_seed=random_seed,
        random_trials=random_trials,
        status="succeeded",
        summary_json=summary,
        report_path=report_path,
    )
    db.add(run)
    db.flush()
    for artifact_type, label, payload in artifacts:
        db.add(
            ModelResearchArtifact(
                run_id=run.id, artifact_type=artifact_type, label=label, payload_json=payload
            )
        )
    db.commit()
    db.refresh(run)
    return run


def latest_research_run(db: Session) -> ModelResearchRun | None:
    return (
        db.query(ModelResearchRun)
        .order_by(ModelResearchRun.created_at.desc(), ModelResearchRun.id.desc())
        .first()
    )


def get_research_run(db: Session, run_id: int) -> ModelResearchRun | None:
    return db.query(ModelResearchRun).filter(ModelResearchRun.id == run_id).one_or_none()


def research_artifacts_by_run(db: Session, run_id: int) -> dict[str, list[ModelResearchArtifact]]:
    rows = (
        db.query(ModelResearchArtifact)
        .filter(ModelResearchArtifact.run_id == run_id)
        .order_by(ModelResearchArtifact.artifact_type.asc(), ModelResearchArtifact.id.asc())
        .all()
    )
    grouped: dict[str, list[ModelResearchArtifact]] = {}
    for row in rows:
        grouped.setdefault(row.artifact_type, []).append(row)
    return grouped


def research_tickets(
    db: Session, run: ModelResearchRun, *, strategy: str | None = None
) -> list[ModelResearchArtifact]:
    selected_strategy = strategy or (run.summary_json or {}).get("best_strategy")
    query = db.query(ModelResearchArtifact).filter(
        ModelResearchArtifact.run_id == run.id,
        ModelResearchArtifact.artifact_type == "combo_ticket",
    )
    if selected_strategy:
        query = query.filter(ModelResearchArtifact.label == selected_strategy)
    return query.order_by(ModelResearchArtifact.id.asc()).all()


def research_ticket_groups(db: Session, run: ModelResearchRun) -> list[dict[str, Any]]:
    """Return model and random-control tickets grouped for report display."""
    best_strategy = (run.summary_json or {}).get("best_strategy")
    if not isinstance(best_strategy, str) or not best_strategy:
        return []

    groups: list[dict[str, Any]] = []
    model_rows = research_tickets(db, run, strategy=best_strategy)
    groups.append(
        _ticket_group(
            group_key=f"model:{best_strategy}",
            title=f"模型最佳策略：{best_strategy}",  # noqa: RUF001
            description="模型选择出的实际二串一方案。",
            rows=model_rows,
        )
    )

    random_rows = (
        db.query(ModelResearchArtifact)
        .filter(
            ModelResearchArtifact.run_id == run.id,
            ModelResearchArtifact.artifact_type == "random_ticket",
        )
        .filter(ModelResearchArtifact.label.like(f"{best_strategy}:%"))
        .order_by(ModelResearchArtifact.label.asc(), ModelResearchArtifact.id.asc())
        .all()
    )
    random_by_label: dict[str, list[ModelResearchArtifact]] = {}
    for row in random_rows:
        random_by_label.setdefault(row.label, []).append(row)

    for label, rows in random_by_label.items():
        control_label = label.split(":", 1)[1] if ":" in label else label
        groups.append(
            _ticket_group(
                group_key=f"random:{label}",
                title=f"对照组：{control_label}",  # noqa: RUF001
                description=(
                    "固定 seed 的随机样本，用于审计随机组选票构成；随机 ROI 以汇总分布为准。"  # noqa: RUF001
                ),
                rows=rows,
            )
        )
    return groups


def _ticket_group(
    *,
    group_key: str,
    title: str,
    description: str,
    rows: list[ModelResearchArtifact],
) -> dict[str, Any]:
    tickets = [row.payload_json for row in rows]
    stake = sum(float(ticket.get("stake", 100.0) or 100.0) for ticket in tickets)
    pnl = sum(float(ticket.get("pnl", 0.0) or 0.0) for ticket in tickets)
    returns = stake + pnl
    roi = pnl / stake if stake else 0.0
    hit_flags = [bool(ticket.get("is_hit")) for ticket in tickets]
    max_hit_streak = _max_streak(hit_flags, target=True)
    max_miss_streak = _max_streak(hit_flags, target=False)
    return {
        "group_key": group_key,
        "title": title,
        "description": description,
        "summary": {
            "ticket_count": len(tickets),
            "stake": round(stake, 4),
            "return": round(returns, 4),
            "returns": round(returns, 4),
            "pnl": round(pnl, 4),
            "roi": round(roi, 8),
            "max_hit_streak": max_hit_streak,
            "max_miss_streak": max_miss_streak,
        },
        "tickets": tickets,
    }


def _max_streak(flags: list[bool], *, target: bool) -> int:
    current = 0
    longest = 0
    for flag in flags:
        if flag is target:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest

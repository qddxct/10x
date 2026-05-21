"""V3.2 过滤器候选模型历史 score 生成脚本。"""

from __future__ import annotations

import argparse
import csv
import io
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import and_, delete
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.engine.service import _pick_odds
from app.models import (
    League,
    ModelConfig,
    SportteryMatch,
    SportteryMatchResult,
    SportteryMatchScore,
    SportteryMatchTeamStats,
)

Row = dict[str, Any]
Channel = Literal["draw", "hdraw"]
V32_CANDIDATE_MODEL_NAME = "empirical-v32-filtered-candidate"


@dataclass(frozen=True)
class Stats:
    bets: int
    hits: int
    hit_rate: float
    pnl: float
    roi: float
    avg_odds: float


@dataclass(frozen=True)
class CandidateRule:
    name: str
    channel: Channel
    bet_type: str
    priority: int
    fn: Callable[[Row], bool]


@dataclass(frozen=True)
class CandidateVersion:
    key: str
    title: str
    model_name: str
    rules: list[CandidateRule]


@dataclass(frozen=True)
class V32ScoreGenerationResult:
    model_config_id: int
    rows: int
    candidates: int
    portfolio: int
    scored_matches: int
    recommended_scores: int
    draw_scores: int
    handicap_draw_scores: int
    replaced_old_scores: int
    report_path: str | None
    csv_path: str | None


def safe_rate(numerator: int | float | None, denominator: int | float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def _sum_ints(*values: int | None) -> int:
    return sum(value or 0 for value in values)


def _form_rate(form: str | None, char: str) -> float | None:
    if not form:
        return None
    text = form.upper()
    return text.count(char) / len(text) if text else None


def enrich_features(row: Row) -> Row:
    item = dict(row)
    item["rank_gap"] = (
        abs(item["home_rank"] - item["away_rank"])
        if item.get("home_rank") is not None and item.get("away_rank") is not None
        else None
    )

    home_season_total = _sum_ints(
        item.get("home_season_wins"),
        item.get("home_season_draws"),
        item.get("home_season_losses"),
    )
    away_season_total = _sum_ints(
        item.get("away_season_wins"),
        item.get("away_season_draws"),
        item.get("away_season_losses"),
    )
    home_venue_total = _sum_ints(
        item.get("home_home_wins"),
        item.get("home_home_draws"),
        item.get("home_home_losses"),
    )
    away_venue_total = _sum_ints(
        item.get("away_away_wins"),
        item.get("away_away_draws"),
        item.get("away_away_losses"),
    )
    h2h_total = _sum_ints(
        item.get("h2h_home_wins"), item.get("h2h_draws"), item.get("h2h_away_wins")
    )

    home_season_draw = safe_rate(item.get("home_season_draws"), home_season_total)
    away_season_draw = safe_rate(item.get("away_season_draws"), away_season_total)
    home_venue_draw = safe_rate(item.get("home_home_draws"), home_venue_total)
    away_venue_draw = safe_rate(item.get("away_away_draws"), away_venue_total)
    home_recent_draw = _form_rate(item.get("home_recent_form"), "D")
    away_recent_draw = _form_rate(item.get("away_recent_form"), "D")

    item["season_draw_sum"] = (
        home_season_draw + away_season_draw
        if home_season_draw is not None and away_season_draw is not None
        else None
    )
    item["venue_draw_sum"] = (
        home_venue_draw + away_venue_draw
        if home_venue_draw is not None and away_venue_draw is not None
        else None
    )
    item["recent_draw_sum"] = (
        home_recent_draw + away_recent_draw
        if home_recent_draw is not None and away_recent_draw is not None
        else None
    )
    item["h2h_draw_rate"] = safe_rate(item.get("h2h_draws"), h2h_total)
    item["home_recent_win_by_1_rate"] = safe_rate(
        item.get("home_recent_win_by_1"), item.get("home_recent_matches_count")
    )
    item["away_recent_loss_by_1_rate"] = safe_rate(
        item.get("away_recent_loss_by_1"), item.get("away_recent_matches_count")
    )
    item["away_recent_loss_by_2plus_rate"] = safe_rate(
        item.get("away_recent_loss_by_2plus"), item.get("away_recent_matches_count")
    )
    item["away_recent_ga_per_match"] = safe_rate(
        item.get("away_recent_goals_against"), item.get("away_recent_matches_count")
    )
    item["h2h_one_goal_margin_rate"] = safe_rate(
        item.get("h2h_one_goal_margin_count"), item.get("h2h_matches_count")
    )
    home_low = safe_rate(
        item.get("home_recent_low_scoring_count"), item.get("home_recent_matches_count")
    )
    away_low = safe_rate(
        item.get("away_recent_low_scoring_count"), item.get("away_recent_matches_count")
    )
    item["recent_low_scoring_sum"] = (
        home_low + away_low if home_low is not None and away_low is not None else None
    )
    return item


def _between(value: float | int | None, low: float, high: float) -> bool:
    return value is not None and low <= float(value) <= high


def _ge(value: float | int | None, threshold: float) -> bool:
    return value is not None and float(value) >= threshold


def _le(value: float | int | None, threshold: float) -> bool:
    return value is not None and float(value) <= threshold


def _hdraw_a0(row: Row) -> bool:
    return (
        _between(row.get("abs_hcap"), 1.00, 1.25)
        and _between(row.get("rank_gap"), 6, 15)
        and _ge(row.get("hhad_d"), 3.50)
        and _ge(row.get("venue_draw_sum"), 0.35)
        and _ge(row.get("season_draw_sum"), 0.35)
    )


def draw_rules() -> list[CandidateRule]:
    return [
        CandidateRule(
            "DRAW_V31_D",
            "draw",
            "draw",
            100,
            lambda row: _ge(row.get("h2h_draw_rate"), 0.35)
            and _ge(row.get("recent_draw_sum"), 0.50)
            and _ge(row.get("recent_low_scoring_sum"), 1.00)
            and _le(row.get("abs_hcap"), 0.50)
            and _between(row.get("had_d"), 3.00, 3.60),
        ),
        CandidateRule(
            "DRAW_V31_A",
            "draw",
            "draw",
            90,
            lambda row: _ge(row.get("h2h_draw_rate"), 0.35)
            and _le(row.get("abs_hcap"), 0.75)
            and _le(row.get("had_d"), 3.80),
        ),
        CandidateRule(
            "DRAW_V31_B",
            "draw",
            "draw",
            80,
            lambda row: _ge(row.get("h2h_one_goal_margin_rate"), 0.35)
            and _ge(row.get("recent_low_scoring_sum"), 1.00)
            and _le(row.get("abs_hcap"), 0.75)
            and row.get("had_d") is not None,
        ),
        CandidateRule(
            "DRAW_V31_C",
            "draw",
            "draw",
            70,
            lambda row: _ge(row.get("recent_draw_sum"), 0.50)
            and _between(row.get("had_d"), 3.00, 3.40)
            and _le(row.get("abs_hcap"), 0.75),
        ),
    ]


def hdraw_rules() -> list[CandidateRule]:
    return [
        CandidateRule(
            "HDRAW_V31_A1",
            "hdraw",
            "handicap_draw",
            100,
            lambda row: _hdraw_a0(row)
            and _ge(row.get("home_recent_win_by_1_rate"), 0.17)
            and _ge(row.get("away_recent_loss_by_1_rate"), 0.17),
        ),
        CandidateRule(
            "HDRAW_V31_A2",
            "hdraw",
            "handicap_draw",
            95,
            lambda row: _hdraw_a0(row)
            and _le(row.get("away_recent_ga_per_match"), 1.60)
            and _le(row.get("away_recent_loss_by_2plus_rate"), 0.34),
        ),
        CandidateRule("HDRAW_V31_A0", "hdraw", "handicap_draw", 90, _hdraw_a0),
        CandidateRule(
            "HDRAW_V31_B",
            "hdraw",
            "handicap_draw",
            80,
            lambda row: _between(row.get("abs_hcap"), 0.75, 1.25)
            and _between(row.get("rank_gap"), 6, 18)
            and _ge(row.get("hhad_d"), 3.40)
            and _ge(row.get("home_recent_win_by_1_rate"), 0.17)
            and _ge(row.get("away_recent_loss_by_1_rate"), 0.17)
            and _le(row.get("away_recent_ga_per_match"), 1.80)
            and _ge(row.get("season_draw_sum"), 0.35)
            and _ge(row.get("venue_draw_sum"), 0.35),
        ),
        CandidateRule(
            "HDRAW_V31_C",
            "hdraw",
            "handicap_draw",
            70,
            lambda row: _ge(row.get("rank_gap"), 16)
            and _between(row.get("abs_hcap"), 1.00, 1.50)
            and _ge(row.get("hhad_d"), 3.40)
            and _le(row.get("away_recent_ga_per_match"), 1.60),
        ),
    ]


def v32_draw_rules() -> list[CandidateRule]:
    v31_by_name = {rule.name: rule for rule in draw_rules()}

    def is_core(row: Row) -> bool:
        return (
            (v31_by_name["DRAW_V31_D"].fn(row) or v31_by_name["DRAW_V31_B"].fn(row))
            and _ge(row.get("had_d"), 3.10)
        )

    return [CandidateRule("DRAW_V32_CORE", "draw", "draw", 90, is_core)]


def v32_hdraw_rules() -> list[CandidateRule]:
    v31_by_name = {rule.name: rule for rule in hdraw_rules()}

    def is_core(row: Row) -> bool:
        return (
            v31_by_name["HDRAW_V31_A0"].fn(row)
            or v31_by_name["HDRAW_V31_A1"].fn(row)
            or v31_by_name["HDRAW_V31_A2"].fn(row)
        )

    return [CandidateRule("HDRAW_V32_CORE", "hdraw", "handicap_draw", 100, is_core)]


def candidate_version(version: str) -> CandidateVersion:
    if version == "v32":
        return CandidateVersion(
            key="v32",
            title="V3.2 过滤器候选模型回测报告",
            model_name=V32_CANDIDATE_MODEL_NAME,
            rules=[*v32_draw_rules(), *v32_hdraw_rules()],
        )
    raise ValueError(f"unsupported candidate version: {version}")


def calculate_stats(rows: Iterable[Row]) -> Stats:
    usable = [row for row in rows if row.get("odds") is not None]
    bets = len(usable)
    hits = sum(1 for row in usable if row.get("hit") is True)
    pnls = [
        (float(row["odds"]) - 1.0) * 100 if row.get("hit") is True else -100.0
        for row in usable
    ]
    avg_odds = sum(float(row["odds"]) for row in usable) / bets if bets else 0.0
    pnl = sum(pnls)
    roi = pnl / (bets * 100) if bets else 0.0
    return Stats(
        bets=bets,
        hits=hits,
        hit_rate=hits / bets if bets else 0.0,
        pnl=pnl,
        roi=roi,
        avg_odds=avg_odds,
    )


def _odds_for(row: Row, channel: Channel) -> float | None:
    value = row.get("had_d") if channel == "draw" else row.get("hhad_d")
    return float(value) if value is not None else None


def _hit_for(row: Row, channel: Channel) -> bool:
    return bool(row.get("is_draw")) if channel == "draw" else bool(row.get("is_hdraw"))


def evaluate_rules(rows: list[Row], rules: list[CandidateRule]) -> list[Row]:
    out: list[Row] = []
    for row in rows:
        for rule in rules:
            if not rule.fn(row):
                continue
            odds = _odds_for(row, rule.channel)
            if odds is None:
                continue
            hit = _hit_for(row, rule.channel)
            out.append(
                {
                    **row,
                    "rule_name": rule.name,
                    "rule_priority": rule.priority,
                    "channel": rule.channel,
                    "bet_type": rule.bet_type,
                    "odds": odds,
                    "hit": hit,
                    "pnl": (odds - 1.0) * 100 if hit else -100.0,
                }
            )
    return out


def portfolio_rows(candidates: list[Row]) -> list[Row]:
    best: dict[int, Row] = {}
    for row in candidates:
        key = int(row["match_id"])
        current = best.get(key)
        rank = _global_priority(row)
        if current is None or rank > _global_priority(current):
            best[key] = row
    return sorted(best.values(), key=lambda row: (row["match_date"], row["match_id"]))


def _global_priority(row: Row) -> int:
    channel_boost = 1000 if row.get("channel") == "hdraw" else 0
    return channel_boost + int(row.get("rule_priority") or 0)


def window_ranges(start: date, end: date, *, days: int = 90) -> list[tuple[date, date]]:
    windows = []
    cursor = start
    while cursor <= end:
        window_end = min(cursor + timedelta(days=days - 1), end)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return windows


def _float(value: Any) -> float | None:
    return float(value) if value is not None else None


def load_rows(db: Session, *, start: date, end: date) -> list[Row]:
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    query = (
        db.query(SportteryMatch, SportteryMatchResult, League, SportteryMatchTeamStats)
        .join(SportteryMatchResult, SportteryMatchResult.match_id == SportteryMatch.id)
        .join(League, League.id == SportteryMatch.league_id)
        .join(SportteryMatchTeamStats, SportteryMatchTeamStats.match_id == SportteryMatch.id)
        .filter(SportteryMatch.match_date >= start_dt, SportteryMatch.match_date <= end_dt)
        .order_by(SportteryMatch.match_date.asc())
    )

    rows: list[Row] = []
    for match, result, league, stats in query:
        odds = _pick_odds(list(match.odds))
        if odds is None:
            continue
        hcap = _float(odds.handicap_value)
        row = {
            "match_id": match.id,
            "match_date": match.match_date.date(),
            "league": league.name,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "is_draw": result.result == "draw",
            "is_hdraw": result.handicap_result == "draw",
            "had_d": _float(match.had_d),
            "hhad_d": _float(match.hhad_d),
            "abs_hcap": abs(hcap) if hcap is not None else None,
            "hcap": hcap,
            "home_rank": stats.home_rank,
            "away_rank": stats.away_rank,
            "home_season_wins": stats.home_season_wins,
            "home_season_draws": stats.home_season_draws,
            "home_season_losses": stats.home_season_losses,
            "away_season_wins": stats.away_season_wins,
            "away_season_draws": stats.away_season_draws,
            "away_season_losses": stats.away_season_losses,
            "home_home_wins": stats.home_home_wins,
            "home_home_draws": stats.home_home_draws,
            "home_home_losses": stats.home_home_losses,
            "away_away_wins": stats.away_away_wins,
            "away_away_draws": stats.away_away_draws,
            "away_away_losses": stats.away_away_losses,
            "home_recent_form": stats.home_recent_form,
            "away_recent_form": stats.away_recent_form,
            "h2h_home_wins": stats.h2h_home_wins,
            "h2h_draws": stats.h2h_draws,
            "h2h_away_wins": stats.h2h_away_wins,
            "home_recent_matches_count": stats.home_recent_matches_count,
            "home_recent_win_by_1": stats.home_recent_win_by_1,
            "home_recent_low_scoring_count": stats.home_recent_low_scoring_count,
            "away_recent_matches_count": stats.away_recent_matches_count,
            "away_recent_loss_by_1": stats.away_recent_loss_by_1,
            "away_recent_loss_by_2plus": stats.away_recent_loss_by_2plus,
            "away_recent_goals_against": stats.away_recent_goals_against,
            "away_recent_low_scoring_count": stats.away_recent_low_scoring_count,
            "h2h_matches_count": stats.h2h_matches_count,
            "h2h_one_goal_margin_count": stats.h2h_one_goal_margin_count,
        }
        rows.append(enrich_features(row))
    return rows


def ensure_candidate_model_config(db: Session, *, model_name: str) -> ModelConfig:
    existing = db.query(ModelConfig).filter(ModelConfig.name == model_name).one_or_none()
    if existing is not None:
        if not existing.is_active:
            db.query(ModelConfig).filter(ModelConfig.id != existing.id).update(
                {"is_active": False}
            )
            existing.is_active = True
            db.commit()
            db.refresh(existing)
        return existing

    cfg = ModelConfig(
        name=model_name,
        created_by=None,
        weights_json={
            "euro": 1,
            "asian": 1,
            "goals": 1,
            "intent": 1,
            "compression": 1,
            "team_stats": 1,
        },
        thresholds_json={
            "strategy": "empirical_v32_filtered",
            "recommend_total_score": 100,
            "draw_min_score": 100,
            "handicap_draw_min_score": 100,
        },
        kelly_bands_json={
            "research_low": {"min_score": 100, "max_score": 107, "kelly_pct": 0.006},
            "research_mid": {"min_score": 108, "max_score": 113, "kelly_pct": 0.010},
            "research_high": {"min_score": 114, "max_score": 120, "kelly_pct": 0.015},
        },
        scrape_schedule_json=None,
        is_active=True,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    db.query(ModelConfig).filter(ModelConfig.id != cfg.id).update({"is_active": False})
    db.commit()
    db.refresh(cfg)
    return cfg


def score_values_for_rule(rule_name: str) -> tuple[int, Decimal]:
    if rule_name == "HDRAW_V32_CORE":
        return 116, Decimal("0.0150")
    if rule_name == "DRAW_V32_CORE":
        return 108, Decimal("0.0100")
    if rule_name in {"HDRAW_V31_A1", "HDRAW_V31_A2"}:
        return 116, Decimal("0.0150")
    if rule_name == "HDRAW_V31_A0":
        return 112, Decimal("0.0120")
    if rule_name == "HDRAW_V31_B":
        return 108, Decimal("0.0100")
    if rule_name == "HDRAW_V31_C":
        return 104, Decimal("0.0080")
    if rule_name == "DRAW_V31_D":
        return 106, Decimal("0.0080")
    return 102, Decimal("0.0060")


def write_scores(
    db: Session,
    portfolio: list[Row],
    *,
    model_config_id: int,
    start: date,
    end: date,
    replace: bool,
) -> dict[str, int]:
    replaced = 0
    if replace:
        start_key = int(f"{start:%Y%m%d}") * 10000
        end_key = int(f"{end:%Y%m%d}") * 10000 + 9999
        result = db.execute(
            delete(SportteryMatchScore).where(
                and_(
                    SportteryMatchScore.model_config_id == model_config_id,
                    SportteryMatchScore.match_id >= start_key,
                    SportteryMatchScore.match_id <= end_key,
                )
            )
        )
        replaced = result.rowcount or 0

    recommended = draw_scores = hdraw_scores = 0
    for row in portfolio:
        total, kelly = score_values_for_rule(str(row["rule_name"]))
        existing = (
            db.query(SportteryMatchScore)
            .filter(
                SportteryMatchScore.match_id == row["match_id"],
                SportteryMatchScore.model_config_id == model_config_id,
            )
            .one_or_none()
        )
        if existing is None:
            existing = SportteryMatchScore(
                match_id=row["match_id"],
                model_config_id=model_config_id,
                user_id=None,
            )
            db.add(existing)
        existing.euro_score = 0
        existing.asian_score = 0
        existing.goals_score = 0
        existing.intent_score = 0
        existing.compression_score = 0
        existing.team_stats_score = total
        existing.total_score = total
        existing.bet_type = row["bet_type"]
        existing.kelly_pct = kelly
        existing.is_recommended = True
        existing.actual_hit = bool(row["hit"])
        existing.notes = _score_notes(row)
        recommended += 1
        if row["bet_type"] == "draw":
            draw_scores += 1
        elif row["bet_type"] == "handicap_draw":
            hdraw_scores += 1

    db.commit()
    return {
        "model_config_id": model_config_id,
        "scored_matches": len(portfolio),
        "recommended_scores": recommended,
        "draw_scores": draw_scores,
        "handicap_draw_scores": hdraw_scores,
        "replaced_old_scores": replaced,
    }


def _score_notes(row: Row) -> str:
    return (
        f"V3.2 candidate only; source_rule={row['rule_name']}; "
        f"rank_gap={row.get('rank_gap')}; abs_hcap={row.get('abs_hcap')}; "
        f"h2h_draw_rate={row.get('h2h_draw_rate')}; "
        f"recent_low_scoring_sum={row.get('recent_low_scoring_sum')}"
    )


def _fmt_pct(value: float) -> str:
    return f"{value:.2%}"


def _fmt_float(value: float) -> str:
    return f"{value:.2f}"


def stats_row(label: str, rows: list[Row]) -> list[Any]:
    stats = calculate_stats(rows)
    return [
        label,
        stats.bets,
        stats.hits,
        _fmt_pct(stats.hit_rate),
        _fmt_pct(stats.roi),
        _fmt_float(stats.avg_odds),
        _fmt_float(stats.pnl),
    ]


def markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return lines


def _group_rows(rows: list[Row], key: str) -> list[list[Any]]:
    groups: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key, "NA"))].append(row)
    return sorted(
        [stats_row(label, group) for label, group in groups.items()],
        key=lambda item: (float(str(item[4]).rstrip("%")), int(item[1])),
        reverse=True,
    )


def _window_rows(rows: list[Row], start: date, end: date) -> list[list[Any]]:
    out = []
    for window_start, window_end in window_ranges(start, end):
        selected = [row for row in rows if window_start <= row["match_date"] <= window_end]
        out.append(stats_row(f"{window_start} 至 {window_end}", selected))
    return out


def _overlap_rows(candidates: list[Row]) -> list[list[Any]]:
    by_match: dict[int, set[str]] = defaultdict(set)
    for row in candidates:
        by_match[int(row["match_id"])].add(str(row["rule_name"]))
    pair_counts: dict[str, int] = defaultdict(int)
    for names in by_match.values():
        ordered = sorted(names)
        for idx, left in enumerate(ordered):
            for right in ordered[idx + 1 :]:
                pair_counts[f"{left} + {right}"] += 1
    sorted_pairs = sorted(
        pair_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    return [[pair, count] for pair, count in sorted_pairs[:20]]


def csv_lines(rows: list[Row]) -> list[str]:
    fields = [
        "match_id",
        "match_date",
        "league",
        "home_team",
        "away_team",
        "rule_name",
        "channel",
        "bet_type",
        "odds",
        "hit",
        "pnl",
        "hcap",
        "rank_gap",
        "had_d",
        "hhad_d",
        "home_recent_win_by_1_rate",
        "away_recent_loss_by_1_rate",
        "away_recent_ga_per_match",
        "h2h_draw_rate",
        "h2h_one_goal_margin_rate",
        "recent_low_scoring_sum",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().splitlines()


def render_report(
    *,
    rows: list[Row],
    candidates: list[Row],
    portfolio: list[Row],
    start: date,
    end: date,
    detail_path: str,
    write_summary: dict[str, int],
    title: str = "V3.2 过滤器候选模型回测报告",
    model_name: str = V32_CANDIDATE_MODEL_NAME,
) -> str:
    draw_candidates = [row for row in candidates if row["channel"] == "draw"]
    hdraw_candidates = [row for row in candidates if row["channel"] == "hdraw"]
    draw_portfolio = [row for row in portfolio if row["channel"] == "draw"]
    hdraw_portfolio = [row for row in portfolio if row["channel"] == "hdraw"]

    lines: list[str] = [
        f"# {title}",
        "",
        f"日期: {datetime.now().date().isoformat()}",
        "",
        "## 1. 数据范围",
        "",
        f"- 数据范围: {start.isoformat()} 至 {end.isoformat()}",
        f"- 入样比赛: {len(rows)}",
        f"- 候选命中行(raw): {len(candidates)}",
        f"- 写入组合场次(portfolio): {len(portfolio)}",
        f"- 候选模型: `{model_name}`",
        f"- 明细文件: `{detail_path}`",
        "",
        "## 2. Score 写入摘要",
        "",
        *markdown_table(
            ["字段", "值"],
            [[key, value] for key, value in write_summary.items()],
        ),
        "",
        "## 3. 组合去重表现",
        "",
        *markdown_table(
            ["组合", "下注数", "命中", "命中率", "ROI", "平均赔率", "盈亏"],
            [
                stats_row("全部组合", portfolio),
                stats_row("普通平组合", draw_portfolio),
                stats_row("让平组合", hdraw_portfolio),
            ],
        ),
        "",
        "## 4. 候选规则独立表现",
        "",
        "### 普通平",
        "",
        *markdown_table(
            ["规则", "下注数", "命中", "命中率", "ROI", "平均赔率", "盈亏"],
            _group_rows(draw_candidates, "rule_name"),
        ),
        "",
        "### 让平",
        "",
        *markdown_table(
            ["规则", "下注数", "命中", "命中率", "ROI", "平均赔率", "盈亏"],
            _group_rows(hdraw_candidates, "rule_name"),
        ),
        "",
        "## 5. 90 天窗口",
        "",
        "### 全部组合",
        "",
        *markdown_table(
            ["窗口", "下注数", "命中", "命中率", "ROI", "平均赔率", "盈亏"],
            _window_rows(portfolio, start, end),
        ),
        "",
        "### 普通平组合",
        "",
        *markdown_table(
            ["窗口", "下注数", "命中", "命中率", "ROI", "平均赔率", "盈亏"],
            _window_rows(draw_portfolio, start, end),
        ),
        "",
        "### 让平组合",
        "",
        *markdown_table(
            ["窗口", "下注数", "命中", "命中率", "ROI", "平均赔率", "盈亏"],
            _window_rows(hdraw_portfolio, start, end),
        ),
        "",
        "## 6. 规则重叠 Top 20",
        "",
        *markdown_table(["规则组合", "重叠场次"], _overlap_rows(candidates)),
        "",
        "## 7. 结论",
        "",
        f"- 本报告已写入当前候选模型 `{model_name}` 的历史 score。",
        "- 该模型用于历史回测页面和二串一研究报告观察; 是否接入今日推荐, 需要单独确认。",
        "- 是否进入下一版模型, 需要基于本报告和回测页面 90 天窗口继续人工确认。",
        "",
    ]
    return "\n".join(lines)


def generate_v32_scores(
    db: Session,
    *,
    start: date,
    end: date,
    report_path: Path | None = None,
    csv_path: Path | None = None,
    replace: bool = True,
) -> V32ScoreGenerationResult:
    version = candidate_version("v32")
    rows = load_rows(db, start=start, end=end)
    candidates = evaluate_rules(rows, version.rules)
    portfolio = portfolio_rows(candidates)
    cfg = ensure_candidate_model_config(db, model_name=version.model_name)
    write_summary = write_scores(
        db,
        portfolio,
        model_config_id=cfg.id,
        start=start,
        end=end,
        replace=replace,
    )

    if csv_path is not None:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text("\n".join(csv_lines(candidates)), encoding="utf-8")

    if report_path is not None:
        report = render_report(
            rows=rows,
            candidates=candidates,
            portfolio=portfolio,
            start=start,
            end=end,
            detail_path=str(csv_path or ""),
            write_summary=write_summary,
            title=version.title,
            model_name=version.model_name,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")

    return V32ScoreGenerationResult(
        model_config_id=int(write_summary["model_config_id"]),
        rows=len(rows),
        candidates=len(candidates),
        portfolio=len(portfolio),
        scored_matches=int(write_summary["scored_matches"]),
        recommended_scores=int(write_summary["recommended_scores"]),
        draw_scores=int(write_summary["draw_scores"]),
        handicap_draw_scores=int(write_summary["handicap_draw_scores"]),
        replaced_old_scores=int(write_summary["replaced_old_scores"]),
        report_path=str(report_path) if report_path else None,
        csv_path=str(csv_path) if csv_path else None,
    )


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=["v32"], default="v32")
    parser.add_argument("--start", default="2024-09-28")
    parser.add_argument("--end", default="2026-04-22")
    parser.add_argument(
        "--report",
        default="docs/analysis/2026-04-26-v32-filtered-candidate-backtest.md",
    )
    parser.add_argument("--csv", default="docs/analysis/v32-filtered-candidates.csv")
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    with SessionLocal() as db:
        result = generate_v32_scores(
            db,
            start=start,
            end=end,
            report_path=Path(args.report),
            csv_path=Path(args.csv),
            replace=args.replace,
        )
    print(
        f"rows={result.rows} candidates={result.candidates} portfolio={result.portfolio} "
        f"scored={result.scored_matches} "
        f"model_config_id={result.model_config_id} "
        f"report={result.report_path} csv={result.csv_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

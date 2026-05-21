"""平/让平增量信号只读验证脚本。"""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.engine.service import _pick_odds
from app.models import (
    League,
    SportteryMatch,
    SportteryMatchResult,
    SportteryMatchTeamStats,
)

Row = dict[str, Any]
Target = str


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
    channel: Target
    family: str
    fn: Any


def safe_rate(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def safe_per_match(value: int | None, matches: int | None) -> float | None:
    return safe_rate(value, matches)


def goal_margin(home_score: int, away_score: int) -> int:
    return home_score - away_score


def roi(pnls: Iterable[float]) -> float:
    values = list(pnls)
    return sum(values) / (len(values) * 100) if values else 0.0


def bucket(value: float | None, edges: list[float], labels: list[str]) -> str:
    if value is None:
        return "NA"
    for idx, (low, high) in enumerate(pairwise(edges)):
        if low <= value < high:
            return labels[idx]
    return labels[-1]


def _odds_key(target: Target) -> str:
    return "had_d" if target == "draw" else "hhad_d"


def _hit_key(target: Target) -> str:
    return "is_draw" if target == "draw" else "is_hdraw"


def calculate_stats(rows: Iterable[Row], *, target: Target) -> Stats:
    odds_key = _odds_key(target)
    hit_key = _hit_key(target)
    usable = [row for row in rows if row.get(odds_key) is not None]
    bets = len(usable)
    hits = sum(1 for row in usable if row[hit_key])
    pnls = [
        (float(row[odds_key]) - 1) * 100 if row[hit_key] else -100
        for row in usable
    ]
    avg_odds = sum(float(row[odds_key]) for row in usable) / bets if bets else 0.0
    return Stats(
        bets=bets,
        hits=hits,
        hit_rate=hits / bets if bets else 0.0,
        pnl=sum(pnls),
        roi=roi(pnls),
        avg_odds=avg_odds,
    )


def is_hdraw_a(row: Row) -> bool:
    hcap = row.get("hcap")
    rank_gap = row.get("rank_gap")
    hhad_d = row.get("hhad_d")
    venue_sum = row.get("venue_draw_sum")
    season_sum = row.get("season_draw_sum")
    if hcap is None or abs(float(hcap)) >= 1.5:
        return False
    if venue_sum is not None and float(venue_sum) < 0.35:
        return False
    if season_sum is not None and float(season_sum) < 0.35:
        return False
    return (
        1.00 <= abs(float(hcap)) <= 1.25
        and rank_gap is not None
        and 6 <= float(rank_gap) <= 15
        and hhad_d is not None
        and float(hhad_d) >= 3.50
    )


def _sum_ints(*values: int | None) -> int:
    return sum(value or 0 for value in values)


def _form_rate(form: str | None, char: str) -> float | None:
    if not form:
        return None
    text = form.upper()
    return text.count(char) / len(text) if text else None


def enrich_row_features(row: Row) -> Row:
    item = dict(row)
    item["goal_margin"] = goal_margin(item["home_score"], item["away_score"])

    if item.get("home_rank") is not None and item.get("away_rank") is not None:
        item["rank_gap"] = abs(item["home_rank"] - item["away_rank"])
    else:
        item["rank_gap"] = None

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
        item.get("h2h_home_wins"),
        item.get("h2h_draws"),
        item.get("h2h_away_wins"),
    )

    home_season_draw = safe_rate(item.get("home_season_draws"), home_season_total)
    away_season_draw = safe_rate(item.get("away_season_draws"), away_season_total)
    home_venue_draw = safe_rate(item.get("home_home_draws"), home_venue_total)
    away_venue_draw = safe_rate(item.get("away_away_draws"), away_venue_total)

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
    item["h2h_draw_rate"] = safe_rate(item.get("h2h_draws"), h2h_total)
    item["home_recent_win_rate"] = _form_rate(item.get("home_recent_form"), "W")
    item["home_recent_draw_rate"] = _form_rate(item.get("home_recent_form"), "D")
    item["away_recent_loss_rate"] = _form_rate(item.get("away_recent_form"), "L")
    item["away_recent_draw_rate"] = _form_rate(item.get("away_recent_form"), "D")
    item["recent_draw_sum"] = (
        item["home_recent_draw_rate"] + item["away_recent_draw_rate"]
        if item["home_recent_draw_rate"] is not None
        and item["away_recent_draw_rate"] is not None
        else None
    )

    item["home_recent_win_by_1_rate"] = safe_rate(
        item.get("home_recent_win_by_1"), item.get("home_recent_matches_count")
    )
    item["away_recent_loss_by_1_rate"] = safe_rate(
        item.get("away_recent_loss_by_1"), item.get("away_recent_matches_count")
    )
    item["home_recent_gf_per_match"] = safe_per_match(
        item.get("home_recent_goals_for"), item.get("home_recent_matches_count")
    )
    item["away_recent_ga_per_match"] = safe_per_match(
        item.get("away_recent_goals_against"), item.get("away_recent_matches_count")
    )
    item["home_home_recent_win_by_1_rate"] = safe_rate(
        item.get("home_home_recent_win_by_1"),
        item.get("home_home_recent_matches_count"),
    )
    item["away_away_recent_loss_by_1_rate"] = safe_rate(
        item.get("away_away_recent_loss_by_1"),
        item.get("away_away_recent_matches_count"),
    )
    item["h2h_one_goal_margin_rate"] = safe_rate(
        item.get("h2h_one_goal_margin_count"), item.get("h2h_matches_count")
    )
    home_low_scoring_rate = safe_rate(
        item.get("home_recent_low_scoring_count"), item.get("home_recent_matches_count")
    )
    away_low_scoring_rate = safe_rate(
        item.get("away_recent_low_scoring_count"), item.get("away_recent_matches_count")
    )
    item["recent_low_scoring_sum"] = (
        home_low_scoring_rate + away_low_scoring_rate
        if home_low_scoring_rate is not None and away_low_scoring_rate is not None
        else None
    )
    return item


def _coverage(rows: list[Row], key: str) -> str:
    total = len(rows)
    present = sum(1 for row in rows if row.get(key) is not None)
    pct = present / total if total else 0.0
    return f"{present}/{total} ({pct:.2%})"


def data_gap_rows(rows: list[Row]) -> list[list[str]]:
    return [
        ["recent_form_wdl", _coverage(rows, "home_recent_form"), "可用: 只有 W/D/L"],
        ["h2h_wdl", _coverage(rows, "h2h_draw_rate"), "可用: 只有胜平负汇总"],
        [
            "structured_recent_scores",
            _coverage(rows, "home_recent_matches_count"),
            "可用: Titan007 近况比分快照",
        ],
        [
            "goals_for_against",
            _coverage(rows, "home_recent_gf_per_match"),
            "可用: 近期进球/失球均值",
        ],
        [
            "one_goal_margin_distribution",
            _coverage(rows, "home_recent_win_by_1_rate"),
            "可用: 一球胜负分布",
        ],
        ["odds_movement_history", "0/0 (0.00%)", "缺失: 赔率/盘口变化轨迹"],
        ["schedule_pressure", "0/0 (0.00%)", "缺失: 赛程压力"],
        ["injury_absence", "0/0 (0.00%)", "缺失: 伤停"],
    ]


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
        raw = {
            "match_id": match.id,
            "match_date": match.match_date.date(),
            "month": match.match_date.strftime("%Y-%m"),
            "league": league.name,
            "competition_type": match.competition_type,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "home_score": result.home_score,
            "away_score": result.away_score,
            "is_draw": result.result == "draw",
            "is_hdraw": result.handicap_result == "draw",
            "had_d": _float(match.had_d),
            "hhad_d": _float(match.hhad_d),
            "hcap": _float(odds.handicap_value),
            "win_odds": _float(odds.win_odds),
            "draw_odds": _float(odds.draw_odds),
            "lose_odds": _float(odds.lose_odds),
            "handicap_draw_odds": _float(odds.draw_handicap_odds),
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
            "home_recent_goals_for": stats.home_recent_goals_for,
            "home_recent_goals_against": stats.home_recent_goals_against,
            "home_recent_win_by_1": stats.home_recent_win_by_1,
            "home_recent_low_scoring_count": stats.home_recent_low_scoring_count,
            "away_recent_matches_count": stats.away_recent_matches_count,
            "away_recent_goals_for": stats.away_recent_goals_for,
            "away_recent_goals_against": stats.away_recent_goals_against,
            "away_recent_loss_by_1": stats.away_recent_loss_by_1,
            "away_recent_low_scoring_count": stats.away_recent_low_scoring_count,
            "home_home_recent_matches_count": stats.home_home_recent_matches_count,
            "home_home_recent_win_by_1": stats.home_home_recent_win_by_1,
            "away_away_recent_matches_count": stats.away_away_recent_matches_count,
            "away_away_recent_loss_by_1": stats.away_away_recent_loss_by_1,
            "h2h_matches_count": stats.h2h_matches_count,
            "h2h_one_goal_margin_count": stats.h2h_one_goal_margin_count,
        }
        rows.append(enrich_row_features(raw))
    return rows


def _fmt_pct(value: float) -> str:
    return f"{value:.2%}"


def _fmt_float(value: float) -> str:
    return f"{value:.2f}"


def stats_row(label: str, stats: Stats) -> list[str | int]:
    return [
        label,
        stats.bets,
        stats.hits,
        _fmt_pct(stats.hit_rate),
        _fmt_pct(stats.roi),
        _fmt_float(stats.avg_odds),
    ]


def bucket_summary(rows: list[Row], *, key: str, target: Target, min_bets: int) -> list[list[Any]]:
    groups: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key, "NA"))].append(row)
    out = []
    for label, group_rows in groups.items():
        stats = calculate_stats(group_rows, target=target)
        if stats.bets >= min_bets:
            out.append(stats_row(label, stats))
    return sorted(out, key=lambda row: (row[4], row[3], row[1]), reverse=True)


def non_overlapping_windows(start: date, end: date, *, days: int) -> list[tuple[date, date]]:
    windows = []
    cursor = start
    while cursor <= end:
        window_end = min(cursor + timedelta(days=days - 1), end)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return windows


def window_summary(rows: list[Row], *, target: Target, start: date, end: date) -> Stats:
    selected = [row for row in rows if start <= row["match_date"] <= end]
    return calculate_stats(selected, target=target)


def add_analysis_buckets(rows: list[Row]) -> list[Row]:
    enriched = []
    for row in rows:
        item = dict(row)
        item["abs_hcap_bucket"] = bucket(
            abs(item["hcap"]) if item.get("hcap") is not None else None,
            [0, 0.26, 0.76, 1.01, 1.26, 1.51, 99],
            ["0-0.25", "0.5-0.75", "1.0", "1.25", "1.5", ">1.5"],
        )
        item["rank_gap_bucket"] = bucket(
            item.get("rank_gap"),
            [0, 3, 6, 11, 16, 99],
            ["0-2", "3-5", "6-10", "11-15", ">=16"],
        )
        item["season_draw_sum_bucket"] = bucket(
            item.get("season_draw_sum"),
            [0, 0.35, 0.45, 0.55, 0.65, 2],
            ["<0.35", "0.35-0.45", "0.45-0.55", "0.55-0.65", ">=0.65"],
        )
        item["venue_draw_sum_bucket"] = bucket(
            item.get("venue_draw_sum"),
            [0, 0.35, 0.45, 0.55, 0.65, 2],
            ["<0.35", "0.35-0.45", "0.45-0.55", "0.55-0.65", ">=0.65"],
        )
        item["h2h_draw_rate_bucket"] = bucket(
            item.get("h2h_draw_rate"),
            [0, 0.2, 0.35, 0.5, 1.1],
            ["<0.20", "0.20-0.35", "0.35-0.50", ">=0.50"],
        )
        item["home_recent_win_bucket"] = bucket(
            item.get("home_recent_win_rate"),
            [0, 0.34, 0.51, 0.67, 1.1],
            ["<0.34", "0.34-0.50", "0.50-0.67", ">=0.67"],
        )
        item["away_recent_loss_bucket"] = bucket(
            item.get("away_recent_loss_rate"),
            [0, 0.34, 0.51, 0.67, 1.1],
            ["<0.34", "0.34-0.50", "0.50-0.67", ">=0.67"],
        )
        item["home_recent_win_by_1_bucket"] = bucket(
            item.get("home_recent_win_by_1_rate"),
            [0, 0.17, 0.34, 0.51, 1.1],
            ["<0.17", "0.17-0.33", "0.34-0.50", ">=0.50"],
        )
        item["away_recent_loss_by_1_bucket"] = bucket(
            item.get("away_recent_loss_by_1_rate"),
            [0, 0.17, 0.34, 0.51, 1.1],
            ["<0.17", "0.17-0.33", "0.34-0.50", ">=0.50"],
        )
        item["home_recent_gf_bucket"] = bucket(
            item.get("home_recent_gf_per_match"),
            [0, 0.8, 1.2, 1.6, 2.1, 99],
            ["<0.8", "0.8-1.2", "1.2-1.6", "1.6-2.1", ">=2.1"],
        )
        item["away_recent_ga_bucket"] = bucket(
            item.get("away_recent_ga_per_match"),
            [0, 0.8, 1.2, 1.6, 2.1, 99],
            ["<0.8", "0.8-1.2", "1.2-1.6", "1.6-2.1", ">=2.1"],
        )
        item["h2h_one_goal_bucket"] = bucket(
            item.get("h2h_one_goal_margin_rate"),
            [0, 0.2, 0.35, 0.5, 1.1],
            ["<0.20", "0.20-0.35", "0.35-0.50", ">=0.50"],
        )
        item["recent_low_scoring_bucket"] = bucket(
            item.get("recent_low_scoring_sum"),
            [0, 0.7, 1.0, 1.3, 2.1],
            ["<0.70", "0.70-1.00", "1.00-1.30", ">=1.30"],
        )
        item["league_group"] = item.get("league") or "NA"
        enriched.append(item)
    return enriched


def draw_candidate_rules() -> list[CandidateRule]:
    return [
        CandidateRule(
            "浅盘口 <= 0.25",
            "draw",
            "hcap",
            lambda row: row.get("hcap") is not None and abs(row["hcap"]) <= 0.25,
        ),
        CandidateRule(
            "澳门平赔 3.00-3.20",
            "draw",
            "draw_odds",
            lambda row: row.get("draw_odds") is not None and 3.00 <= row["draw_odds"] <= 3.20,
        ),
        CandidateRule(
            "排名差 <= 5",
            "draw",
            "rank",
            lambda row: row.get("rank_gap") is not None and row["rank_gap"] <= 5,
        ),
        CandidateRule(
            "H2H 平局率 >= 0.35",
            "draw",
            "h2h",
            lambda row: row.get("h2h_draw_rate") is not None and row["h2h_draw_rate"] >= 0.35,
        ),
        CandidateRule(
            "近期平率和 >= 0.50",
            "draw",
            "recent",
            lambda row: row.get("recent_draw_sum") is not None and row["recent_draw_sum"] >= 0.50,
        ),
        CandidateRule(
            "低比分倾向和 >= 1.00",
            "draw",
            "draw_low_scoring_balance",
            lambda row: row.get("recent_low_scoring_sum") is not None
            and row["recent_low_scoring_sum"] >= 1.00,
        ),
        CandidateRule(
            "H2H 一球差率 >= 0.35",
            "draw",
            "h2h_one_goal_shape",
            lambda row: row.get("h2h_one_goal_margin_rate") is not None
            and row["h2h_one_goal_margin_rate"] >= 0.35,
        ),
    ]


def hdraw_candidate_rules() -> list[CandidateRule]:
    return [
        CandidateRule("HDRAW_A 当前规则", "hdraw", "baseline", is_hdraw_a),
        CandidateRule(
            "H2H 平局率 >= 0.35",
            "hdraw",
            "h2h",
            lambda row: row.get("h2h_draw_rate") is not None and row["h2h_draw_rate"] >= 0.35,
        ),
        CandidateRule(
            "主队近期胜率 < 0.67",
            "hdraw",
            "recent_home",
            lambda row: row.get("home_recent_win_rate") is not None
            and row["home_recent_win_rate"] < 0.67,
        ),
        CandidateRule(
            "客队近期负率 < 0.67",
            "hdraw",
            "recent_away",
            lambda row: row.get("away_recent_loss_rate") is not None
            and row["away_recent_loss_rate"] < 0.67,
        ),
        CandidateRule(
            "主客场平率和 0.35-0.65",
            "hdraw",
            "venue",
            lambda row: row.get("venue_draw_sum") is not None
            and 0.35 <= row["venue_draw_sum"] < 0.65,
        ),
        CandidateRule(
            "主近一球胜 + 客近一球负",
            "hdraw",
            "hdraw_one_goal_shape",
            lambda row: row.get("home_recent_win_by_1_rate") is not None
            and row.get("away_recent_loss_by_1_rate") is not None
            and row["home_recent_win_by_1_rate"] >= 0.17
            and row["away_recent_loss_by_1_rate"] >= 0.17,
        ),
        CandidateRule(
            "客队近期失球 <= 1.60",
            "hdraw",
            "hdraw_defense_risk_filter",
            lambda row: row.get("away_recent_ga_per_match") is not None
            and row["away_recent_ga_per_match"] <= 1.60,
        ),
        CandidateRule(
            "低比分倾向和 >= 1.00",
            "hdraw",
            "draw_low_scoring_balance",
            lambda row: row.get("recent_low_scoring_sum") is not None
            and row["recent_low_scoring_sum"] >= 1.00,
        ),
    ]


def evaluate_rule(rows: list[Row], rule: CandidateRule) -> list[Row]:
    return [row for row in rows if rule.fn(row)]


def candidate_rule_summary(
    rows: list[Row], *, rules: list[CandidateRule], min_bets: int
) -> list[list[Any]]:
    out = []
    for rule in rules:
        selected = evaluate_rule(rows, rule)
        stats = calculate_stats(selected, target=rule.channel)
        if stats.bets >= min_bets:
            out.append(stats_row(rule.name, stats))
    return sorted(out, key=lambda row: (row[4], row[3], row[1]), reverse=True)


def markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return lines


def baseline_rows(rows: list[Row]) -> list[list[Any]]:
    return [
        stats_row("普通平全样本", calculate_stats(rows, target="draw")),
        stats_row("让平全样本", calculate_stats(rows, target="hdraw")),
        stats_row(
            "HDRAW_A 当前规则",
            calculate_stats([row for row in rows if is_hdraw_a(row)], target="hdraw"),
        ),
    ]


def window_rows(
    rows: list[Row], *, target: Target, start: date, end: date, days: int
) -> list[list[Any]]:
    out = []
    for window_start, window_end in non_overlapping_windows(start, end, days=days):
        stats = window_summary(rows, target=target, start=window_start, end=window_end)
        out.append(stats_row(f"{window_start} 至 {window_end}", stats))
    return out


def render_report(rows: list[Row], *, start: date, end: date) -> str:
    rows = add_analysis_buckets(rows)
    lines: list[str] = [
        "# V3.1/V4 增量信号验证报告",
        "",
        "日期: 2026-04-26",
        f"数据范围: {start.isoformat()} 至 {end.isoformat()}",
        "",
        "## 1. 数据完整性",
        "",
        *markdown_table(["维度", "覆盖率", "状态"], data_gap_rows(rows)),
        "",
        "## 2. 当前基线",
        "",
        *markdown_table(
            ["目标", "下注数", "命中", "命中率", "ROI", "平均赔率"],
            baseline_rows(rows),
        ),
        "",
        "## 3. Draw Channel 单变量分桶",
        "",
    ]

    bucket_keys = [
        "abs_hcap_bucket",
        "rank_gap_bucket",
        "season_draw_sum_bucket",
        "venue_draw_sum_bucket",
        "h2h_draw_rate_bucket",
        "home_recent_win_bucket",
        "away_recent_loss_bucket",
        "home_recent_win_by_1_bucket",
        "away_recent_loss_by_1_bucket",
        "home_recent_gf_bucket",
        "away_recent_ga_bucket",
        "h2h_one_goal_bucket",
        "recent_low_scoring_bucket",
        "league_group",
    ]
    for key in bucket_keys:
        lines.extend(
            [
                f"### {key}",
                "",
                *markdown_table(
                    ["分桶", "下注数", "命中", "命中率", "ROI", "平均赔率"],
                    bucket_summary(rows, key=key, target="draw", min_bets=20),
                ),
                "",
            ]
        )

    lines.extend(["## 4. Handicap Draw Channel 单变量分桶", ""])
    for key in bucket_keys:
        lines.extend(
            [
                f"### {key}",
                "",
                *markdown_table(
                    ["分桶", "下注数", "命中", "命中率", "ROI", "平均赔率"],
                    bucket_summary(rows, key=key, target="hdraw", min_bets=20),
                ),
                "",
            ]
        )

    lines.extend(
        [
            "## 5. 候选规则",
            "",
            "### Draw Channel",
            "",
            *markdown_table(
                ["规则", "下注数", "命中", "命中率", "ROI", "平均赔率"],
                candidate_rule_summary(rows, rules=draw_candidate_rules(), min_bets=25),
            ),
            "",
            "### Handicap Draw Channel",
            "",
            *markdown_table(
                ["规则", "下注数", "命中", "命中率", "ROI", "平均赔率"],
                candidate_rule_summary(rows, rules=hdraw_candidate_rules(), min_bets=25),
            ),
            "",
            "## 6. 90 天窗口",
            "",
            "### Draw Channel",
            "",
            *markdown_table(
                ["窗口", "下注数", "命中", "命中率", "ROI", "平均赔率"],
                window_rows(rows, target="draw", start=start, end=end, days=90),
            ),
            "",
            "### Handicap Draw Channel",
            "",
            *markdown_table(
                ["窗口", "下注数", "命中", "命中率", "ROI", "平均赔率"],
                window_rows(rows, target="hdraw", start=start, end=end, days=90),
            ),
            "",
            "## 7. 初步结论",
            "",
            "- 本报告只做增量信号验证, 不修改模型。",
            "- 当前已补入 Titan007 近期比分、进失球、一球胜负和低比分倾向快照。",
            "- 赔率/盘口变化轨迹、赛程压力、伤停仍是关键数据缺口。",
            "- 是否进入 V3.1/V4 必须基于本报告和人工复核。",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2024-09-28")
    parser.add_argument("--end", default="2026-04-22")
    parser.add_argument(
        "--report",
        default="docs/analysis/2026-04-26-v31-v4-incremental-signal-validation.md",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    with SessionLocal() as db:
        rows = load_rows(db, start=start, end=end)
    report = render_report(rows, start=start, end=end)
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    print(f"rows={len(rows)} report={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

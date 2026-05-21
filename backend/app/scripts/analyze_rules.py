"""Analyze historical rule candidates for draw and handicap-draw bets.

This is a read-only research script. It computes feature buckets and candidate
rule combinations from historical matches, odds, results, and team snapshots.

Usage:
    MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308 PYTHONPATH=backend \
      backend/.venv/bin/python -m app.scripts.analyze_rules
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import combinations, pairwise
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

Target = str
Row = dict[str, Any]


@dataclass(frozen=True)
class Stats:
    bets: int
    hits: int
    hit_rate: float
    pnl: float
    roi: float
    avg_odds: float


@dataclass(frozen=True)
class Predicate:
    name: str
    family: str
    fn: Callable[[Row], bool]


def _float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _ratio(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or not denominator:
        return None
    return numerator / denominator


def _form_rates(form: str | None) -> dict[str, float | None]:
    if not form:
        return {"w": None, "d": None, "l": None}
    text = form.upper()
    total = len(text)
    if total <= 0:
        return {"w": None, "d": None, "l": None}
    return {
        "w": text.count("W") / total,
        "d": text.count("D") / total,
        "l": text.count("L") / total,
    }


def _sum_ints(values: Iterable[int | None]) -> int:
    return sum(value or 0 for value in values)


def _settlement_odds_key(target: Target) -> str:
    return "had_d" if target == "draw" else "hhad_d"


def _hit_key(target: Target) -> str:
    return "is_draw" if target == "draw" else "is_hdraw"


def calculate_stats(rows: Iterable[Row], target: Target) -> Stats:
    odds_key = _settlement_odds_key(target)
    hit_key = _hit_key(target)
    usable = [row for row in rows if row.get(odds_key) is not None]
    bets = len(usable)
    hits = sum(1 for row in usable if row[hit_key])
    pnl = sum((row[odds_key] - 1) * 100 if row[hit_key] else -100 for row in usable)
    avg_odds = sum(row[odds_key] for row in usable) / bets if bets else 0.0
    return Stats(
        bets=bets,
        hits=hits,
        hit_rate=hits / bets if bets else 0.0,
        pnl=pnl,
        roi=pnl / (bets * 100) if bets else 0.0,
        avg_odds=avg_odds,
    )


def load_rows(db: Session) -> list[Row]:
    query = (
        db.query(SportteryMatch, SportteryMatchResult, League, SportteryMatchTeamStats)
        .join(SportteryMatchResult, SportteryMatchResult.match_id == SportteryMatch.id)
        .join(League, League.id == SportteryMatch.league_id)
        .join(SportteryMatchTeamStats, SportteryMatchTeamStats.match_id == SportteryMatch.id)
    )

    rows: list[Row] = []
    for match, result, league, stats in query:
        odds = _pick_odds(list(match.odds))
        if odds is None:
            continue

        home_season_total = _sum_ints(
            [
                stats.home_season_wins,
                stats.home_season_draws,
                stats.home_season_losses,
            ]
        )
        away_season_total = _sum_ints(
            [
                stats.away_season_wins,
                stats.away_season_draws,
                stats.away_season_losses,
            ]
        )
        home_venue_total = _sum_ints(
            [stats.home_home_wins, stats.home_home_draws, stats.home_home_losses]
        )
        away_venue_total = _sum_ints(
            [stats.away_away_wins, stats.away_away_draws, stats.away_away_losses]
        )
        h2h_total = _sum_ints(
            [stats.h2h_home_wins, stats.h2h_draws, stats.h2h_away_wins]
        )

        home_season_draw_rate = _ratio(stats.home_season_draws, home_season_total)
        away_season_draw_rate = _ratio(stats.away_season_draws, away_season_total)
        home_venue_draw_rate = _ratio(stats.home_home_draws, home_venue_total)
        away_venue_draw_rate = _ratio(stats.away_away_draws, away_venue_total)
        h2h_draw_rate = _ratio(stats.h2h_draws, h2h_total)
        home_recent = _form_rates(stats.home_recent_form)
        away_recent = _form_rates(stats.away_recent_form)

        macau_odds = [
            _float(odds.win_odds),
            _float(odds.draw_odds),
            _float(odds.lose_odds),
        ]
        sporttery_odds = [
            _float(match.had_h),
            _float(match.had_d),
            _float(match.had_a),
        ]
        macau_spread = (
            max(macau_odds) - min(macau_odds)
            if all(value is not None for value in macau_odds)
            else None
        )
        sporttery_spread = (
            max(sporttery_odds) - min(sporttery_odds)
            if all(value is not None for value in sporttery_odds)
            else None
        )

        rows.append(
            {
                "match_id": match.id,
                "date": match.match_date.date().isoformat(),
                "month": match.match_date.strftime("%Y-%m"),
                "league": league.name,
                "is_draw": result.result == "draw",
                "is_hdraw": result.handicap_result == "draw",
                "hcap": _float(odds.handicap_value),
                "hhad_goal_line": _float(match.hhad_goal_line),
                "draw_odds": _float(odds.draw_odds),
                "had_d": _float(match.had_d),
                "hhad_d": _float(match.hhad_d),
                "macau_spread": macau_spread,
                "sporttery_spread": sporttery_spread,
                "rank_gap": (
                    abs(stats.home_rank - stats.away_rank)
                    if stats.home_rank is not None and stats.away_rank is not None
                    else None
                ),
                "home_season_draw_rate": home_season_draw_rate,
                "away_season_draw_rate": away_season_draw_rate,
                "season_draw_sum": (
                    home_season_draw_rate + away_season_draw_rate
                    if home_season_draw_rate is not None
                    and away_season_draw_rate is not None
                    else None
                ),
                "home_venue_draw_rate": home_venue_draw_rate,
                "away_venue_draw_rate": away_venue_draw_rate,
                "venue_draw_sum": (
                    home_venue_draw_rate + away_venue_draw_rate
                    if home_venue_draw_rate is not None
                    and away_venue_draw_rate is not None
                    else None
                ),
                "recent_draw_sum": (
                    home_recent["d"] + away_recent["d"]
                    if home_recent["d"] is not None and away_recent["d"] is not None
                    else None
                ),
                "home_recent_win_rate": home_recent["w"],
                "away_recent_loss_rate": away_recent["l"],
                "h2h_draw_rate": h2h_draw_rate,
            }
        )
    return sorted(rows, key=lambda row: row["date"])


def _fmt_pct(value: float) -> str:
    return f"{value:.2%}"


def _fmt_float(value: float) -> str:
    return f"{value:.2f}"


def print_table(headers: list[str], rows: list[list[Any]]) -> None:
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        print("| " + " | ".join(str(value) for value in row) + " |")


def bucket(value: float | None, edges: list[float], labels: list[str]) -> str:
    if value is None:
        return "NA"
    for idx, (low, high) in enumerate(pairwise(edges)):
        if low <= value < high:
            return labels[idx]
    return labels[-1]


def enrich_buckets(rows: list[Row]) -> list[Row]:
    enriched = []
    for row in rows:
        item = dict(row)
        item["hcap_bucket"] = str(row["hcap"])
        item["abs_hcap_bucket"] = bucket(
            abs(row["hcap"]) if row["hcap"] is not None else None,
            [0, 0.01, 0.26, 0.51, 0.76, 1.01, 1.51, 99],
            ["0", "0.25", "0.5", "0.75", "1.0", "1.25-1.5", ">1.5"],
        )
        item["draw_odds_bucket"] = bucket(
            row["draw_odds"],
            [0, 2.8, 3.0, 3.2, 3.4, 3.6, 99],
            ["<2.8", "2.8-3.0", "3.0-3.2", "3.2-3.4", "3.4-3.6", ">=3.6"],
        )
        item["had_d_bucket"] = bucket(
            row["had_d"],
            [0, 2.7, 2.9, 3.1, 3.3, 3.5, 99],
            ["<2.7", "2.7-2.9", "2.9-3.1", "3.1-3.3", "3.3-3.5", ">=3.5"],
        )
        item["season_draw_sum_bucket"] = bucket(
            row["season_draw_sum"],
            [0, 0.35, 0.45, 0.55, 0.65, 2],
            ["<.35", ".35-.45", ".45-.55", ".55-.65", ">=.65"],
        )
        item["venue_draw_sum_bucket"] = bucket(
            row["venue_draw_sum"],
            [0, 0.35, 0.45, 0.55, 0.65, 2],
            ["<.35", ".35-.45", ".45-.55", ".55-.65", ">=.65"],
        )
        item["rank_gap_bucket"] = bucket(
            row["rank_gap"],
            [0, 3, 6, 11, 21, 99],
            ["0-2", "3-5", "6-10", "11-20", ">20"],
        )
        enriched.append(item)
    return enriched


def group_summary(
    rows: list[Row],
    *,
    key: str,
    target: Target,
    min_bets: int,
    top: int,
) -> list[list[Any]]:
    groups: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        groups[str(row[key])].append(row)

    summaries = []
    for label, group_rows in groups.items():
        stats = calculate_stats(group_rows, target)
        if stats.bets >= min_bets:
            summaries.append((label, stats))

    summaries.sort(key=lambda item: (item[1].roi, item[1].hit_rate, item[1].bets), reverse=True)
    return [
        [
            label,
            stats.bets,
            stats.hits,
            _fmt_pct(stats.hit_rate),
            _fmt_pct(stats.roi),
            _fmt_float(stats.avg_odds),
        ]
        for label, stats in summaries[:top]
    ]


def draw_predicates() -> list[Predicate]:
    drawish_leagues = {"葡超", "德甲", "韩职", "瑞超", "日职", "意甲", "日乙"}
    bad_leagues = {"西甲", "英冠", "英超", "英甲"}
    return [
        Predicate(
            "主客场平率和 >= 0.65",
            "venue_draw",
            lambda row: row["venue_draw_sum"] is not None and row["venue_draw_sum"] >= 0.65,
        ),
        Predicate(
            "赛季平率和 >= 0.65",
            "season_draw",
            lambda row: row["season_draw_sum"] is not None
            and row["season_draw_sum"] >= 0.65,
        ),
        Predicate(
            "赛季平率和 >= 0.55",
            "season_draw",
            lambda row: row["season_draw_sum"] is not None
            and row["season_draw_sum"] >= 0.55,
        ),
        Predicate(
            "澳门平赔 2.8-3.2",
            "draw_odds",
            lambda row: row["draw_odds"] is not None and 2.8 <= row["draw_odds"] < 3.2,
        ),
        Predicate(
            "澳门平赔 3.0-3.4",
            "draw_odds",
            lambda row: row["draw_odds"] is not None and 3.0 <= row["draw_odds"] < 3.4,
        ),
        Predicate(
            "排名差 <= 5",
            "rank",
            lambda row: row["rank_gap"] is not None and row["rank_gap"] <= 5,
        ),
        Predicate(
            "排名差 <= 2",
            "rank",
            lambda row: row["rank_gap"] is not None and row["rank_gap"] <= 2,
        ),
        Predicate("盘口平手", "hcap", lambda row: row["hcap"] == 0.0),
        Predicate(
            "浅盘 abs(hcap)<=0.25",
            "hcap",
            lambda row: row["hcap"] is not None and abs(row["hcap"]) <= 0.25,
        ),
        Predicate(
            "近期平率和 >= 0.5",
            "recent_draw",
            lambda row: row["recent_draw_sum"] is not None
            and row["recent_draw_sum"] >= 0.5,
        ),
        Predicate("偏平联赛", "league", lambda row: row["league"] in drawish_leagues),
        Predicate("避开低效联赛", "league", lambda row: row["league"] not in bad_leagues),
    ]


def handicap_draw_predicates() -> list[Predicate]:
    return [
        Predicate("盘口 1.0/1.25", "hcap", lambda row: row["hcap"] in (1.0, 1.25)),
        Predicate("盘口 1.25", "hcap", lambda row: row["hcap"] == 1.25),
        Predicate(
            "主客场平率和 < 0.45",
            "venue_draw",
            lambda row: row["venue_draw_sum"] is not None and row["venue_draw_sum"] < 0.45,
        ),
        Predicate(
            "赛季平率和 < 0.45",
            "season_draw",
            lambda row: row["season_draw_sum"] is not None
            and row["season_draw_sum"] < 0.45,
        ),
        Predicate(
            "澳门平赔 3.0-3.2",
            "draw_odds",
            lambda row: row["draw_odds"] is not None and 3.0 <= row["draw_odds"] < 3.2,
        ),
        Predicate(
            "主队近期不热",
            "home_form",
            lambda row: row["home_recent_win_rate"] is not None
            and row["home_recent_win_rate"] <= 0.5,
        ),
        Predicate(
            "客队近期不太差",
            "away_form",
            lambda row: row["away_recent_loss_rate"] is not None
            and row["away_recent_loss_rate"] <= 0.5,
        ),
        Predicate(
            "排名差 >= 6",
            "rank",
            lambda row: row["rank_gap"] is not None and row["rank_gap"] >= 6,
        ),
        Predicate(
            "让平赔率 >= 3.5",
            "hhad_odds",
            lambda row: row["hhad_d"] is not None and row["hhad_d"] >= 3.5,
        ),
    ]


def search_combinations(
    rows: list[Row],
    *,
    predicates: list[Predicate],
    target: Target,
    min_bets: int,
    top: int,
) -> list[list[Any]]:
    candidates = []
    for size in (1, 2, 3):
        for combo in combinations(predicates, size):
            families = [predicate.family for predicate in combo]
            if len(families) != len(set(families)):
                continue
            selected = [row for row in rows if all(predicate.fn(row) for predicate in combo)]
            stats = calculate_stats(selected, target)
            if stats.bets >= min_bets:
                candidates.append((" + ".join(predicate.name for predicate in combo), stats))

    candidates.sort(key=lambda item: (item[1].roi, item[1].hit_rate, item[1].bets), reverse=True)
    return [
        [
            name,
            stats.bets,
            stats.hits,
            _fmt_pct(stats.hit_rate),
            _fmt_pct(stats.roi),
            _fmt_float(stats.avg_odds),
        ]
        for name, stats in candidates[:top]
    ]


def stability_rows(
    rows: list[Row],
    *,
    name: str,
    fn: Callable[[Row], bool],
    target: Target,
    train_cutoff: str,
    test_start: str,
) -> list[list[Any]]:
    selected = [row for row in rows if fn(row)]
    windows = [
        ("all", selected),
        (f"train <= {train_cutoff}", [row for row in selected if row["date"] <= train_cutoff]),
        (f"test >= {test_start}", [row for row in selected if row["date"] >= test_start]),
    ]
    table = []
    for label, window_rows in windows:
        stats = calculate_stats(window_rows, target)
        table.append(
            [
                name,
                label,
                stats.bets,
                stats.hits,
                _fmt_pct(stats.hit_rate),
                _fmt_pct(stats.roi),
                _fmt_float(stats.avg_odds),
            ]
        )
    return table


def run(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        rows = load_rows(db)
    enriched = enrich_buckets(rows)

    print("# Rule Analysis")
    print()
    print(f"- rows: {len(rows)}")
    print(f"- train cutoff: {args.train_cutoff}")
    print(f"- test start: {args.test_start}")
    print()

    print("## Baseline")
    print_table(
        ["target", "bets", "hits", "hit_rate", "roi", "avg_odds"],
        [
            [
                "draw",
                calculate_stats(rows, "draw").bets,
                calculate_stats(rows, "draw").hits,
                _fmt_pct(calculate_stats(rows, "draw").hit_rate),
                _fmt_pct(calculate_stats(rows, "draw").roi),
                _fmt_float(calculate_stats(rows, "draw").avg_odds),
            ],
            [
                "handicap_draw",
                calculate_stats(rows, "hdraw").bets,
                calculate_stats(rows, "hdraw").hits,
                _fmt_pct(calculate_stats(rows, "hdraw").hit_rate),
                _fmt_pct(calculate_stats(rows, "hdraw").roi),
                _fmt_float(calculate_stats(rows, "hdraw").avg_odds),
            ],
        ],
    )
    print()

    bucket_keys = [
        "venue_draw_sum_bucket",
        "season_draw_sum_bucket",
        "draw_odds_bucket",
        "had_d_bucket",
        "hcap_bucket",
        "rank_gap_bucket",
        "league",
    ]
    for target in ("draw", "hdraw"):
        print(f"## Buckets: {target}")
        for key in bucket_keys:
            print()
            print(f"### {key}")
            print_table(
                ["bucket", "bets", "hits", "hit_rate", "roi", "avg_odds"],
                group_summary(
                    enriched,
                    key=key,
                    target=target,
                    min_bets=args.min_bucket_bets,
                    top=args.top,
                ),
            )
        print()

    print("## Candidate Rules: draw")
    print_table(
        ["rule", "bets", "hits", "hit_rate", "roi", "avg_odds"],
        search_combinations(
            rows,
            predicates=draw_predicates(),
            target="draw",
            min_bets=args.min_rule_bets,
            top=args.top,
        ),
    )
    print()

    print("## Candidate Rules: handicap_draw")
    print_table(
        ["rule", "bets", "hits", "hit_rate", "roi", "avg_odds"],
        search_combinations(
            rows,
            predicates=handicap_draw_predicates(),
            target="hdraw",
            min_bets=args.min_rule_bets,
            top=args.top,
        ),
    )
    print()

    stable_rules = [
        (
            "D: 主客场平率和>=0.65",
            lambda row: row["venue_draw_sum"] is not None and row["venue_draw_sum"] >= 0.65,
            "draw",
        ),
        (
            "D: 赛季平率和>=0.65 且 主客场平率和>=0.55",
            lambda row: row["season_draw_sum"] is not None
            and row["venue_draw_sum"] is not None
            and row["season_draw_sum"] >= 0.65
            and row["venue_draw_sum"] >= 0.55,
            "draw",
        ),
        (
            "HD: hcap 1.0/1.25 且 主客场平率和<0.45",
            lambda row: row["hcap"] in (1.0, 1.25)
            and row["venue_draw_sum"] is not None
            and row["venue_draw_sum"] < 0.45,
            "hdraw",
        ),
        (
            "HD: hcap 0/0.25 + 平赔3.0-3.2 + 主队不热",
            lambda row: row["hcap"] in (0.0, 0.25)
            and row["draw_odds"] is not None
            and 3.0 <= row["draw_odds"] < 3.2
            and row["home_recent_win_rate"] is not None
            and row["home_recent_win_rate"] <= 0.5,
            "hdraw",
        ),
    ]
    print("## Stability")
    stability_table = []
    for name, fn, target in stable_rules:
        stability_table.extend(
            stability_rows(
                rows,
                name=name,
                fn=fn,
                target=target,
                train_cutoff=args.train_cutoff,
                test_start=args.test_start,
            )
        )
    print_table(
        ["rule", "window", "bets", "hits", "hit_rate", "roi", "avg_odds"],
        stability_table,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-bucket-bets", type=int, default=20)
    parser.add_argument("--min-rule-bets", type=int, default=25)
    parser.add_argument("--top", type=int, default=12)
    parser.add_argument("--train-cutoff", default="2025-12-31")
    parser.add_argument("--test-start", default="2026-01-01")
    return parser.parse_args()


def main() -> int:
    run(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

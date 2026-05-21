"""Generate V3.4 combo selector research report."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.core.database import SessionLocal
from app.research.combo import summarize_combo_tickets
from app.research.combo_selector import (
    CONSERVATIVE_NEGATIVE_LEAGUES,
    NEGATIVE_LEAGUES,
    PROFILE_ODDS_RANGE,
    SelectorStrategy,
    select_combo_tickets,
)
from app.research.random_baseline import run_random_combo_baseline, sample_random_combo_tickets
from app.research.repository import (
    get_model_config_id,
    load_market_candidates,
    load_model_candidates,
    replace_existing_run,
    save_research_run,
)
from app.research.types import ComboTicket, ResearchCandidate

RUN_NAME = "v34-combo-selector"
STAKE_PER_TICKET = 100.0
STRATEGIES: tuple[SelectorStrategy, ...] = (
    "balanced_selector",
    "conservative_selector",
    "frequency_selector",
)


@dataclass(frozen=True)
class ComboSelectorReportResult:
    run_id: int
    candidates: int
    combo_summaries: int
    random_baselines: int
    report_path: str
    tickets_csv: str
    random_csv: str
    summary: dict[str, Any]


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _total_days(start: date, end: date) -> int:
    return (end - start).days + 1


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({key for row in rows for key in row})
    preferred = ["strategy", "label", "ticket_date", "leg_a", "leg_b"]
    fieldnames = [key for key in preferred if key in keys] + [
        key for key in keys if key not in preferred
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _ticket_row(strategy: str, ticket: ComboTicket) -> dict[str, Any]:
    a, b = ticket.legs
    return {
        "strategy": strategy,
        "ticket_date": ticket.ticket_date.isoformat(),
        "leg_a": a.match_id,
        "leg_b": b.match_id,
        "leg_a_type": a.bet_type,
        "leg_b_type": b.bet_type,
        "leg_a_league": a.league,
        "leg_b_league": b.league,
        "leg_a_odds": a.odds,
        "leg_b_odds": b.odds,
        "combo_odds": ticket.combo_odds,
        "is_hit": ticket.is_hit,
        "pnl": ticket.pnl,
    }


def _format_handicap(value: float | None) -> str:
    if value is None:
        return ""
    formatted = f"{value:g}"
    return formatted if formatted.startswith("-") else f"+{formatted}"


def _bet_label(candidate: ResearchCandidate) -> str:
    if candidate.bet_type == "draw":
        return "平"
    suffix = _format_handicap(candidate.handicap_value)
    return f"让平 ({suffix})" if suffix else "让平"


def _leg_payload(candidate: ResearchCandidate) -> dict[str, Any]:
    return {
        "match_id": candidate.match_id,
        "match_date": candidate.match_date.isoformat(),
        "league": candidate.league,
        "home_team": candidate.home_team,
        "away_team": candidate.away_team,
        "bet_type": candidate.bet_type,
        "bet_label": _bet_label(candidate),
        "handicap_value": candidate.handicap_value,
        "odds": candidate.odds,
        "is_hit": candidate.is_hit,
        "result_label": candidate.result_label or ("命中" if candidate.is_hit else "未命中"),
        "total_score": candidate.total_score,
    }


def _ticket_payload(strategy: str, ticket: ComboTicket) -> dict[str, Any]:
    return {
        "strategy": strategy,
        "ticket_date": ticket.ticket_date.isoformat(),
        "combo_odds": ticket.combo_odds,
        "stake": STAKE_PER_TICKET,
        "is_hit": ticket.is_hit,
        "pnl": ticket.pnl,
        "legs": [_leg_payload(leg) for leg in ticket.legs],
    }


def _random_ticket_payload(
    strategy: str, control_label: str, ticket: ComboTicket
) -> dict[str, Any]:
    payload = _ticket_payload(strategy, ticket)
    payload["group_type"] = "random_control"
    payload["control_label"] = control_label
    return payload


def _strategy_rules(strategy: str | None) -> dict[str, Any]:
    if strategy == "frequency_selector":
        low, high = PROFILE_ODDS_RANGE["frequency"]
        return {
            "strategy": strategy,
            "combo_odds_range": f"{low:g}-{high:g}",
            "excluded_leagues": sorted(NEGATIVE_LEAGUES),
            "ticket_window": "两天滚动组单",
            "frequency": "每个滚动窗口最多一单, 已入选比赛不重复使用",
            "mixed_bet_policy": "允许平/让平混合, 但不额外加分",
        }
    if strategy == "conservative_selector":
        low, high = PROFILE_ODDS_RANGE["conservative"]
        return {
            "strategy": strategy,
            "combo_odds_range": f"{low:g}-{high:g}",
            "excluded_leagues": sorted(CONSERVATIVE_NEGATIVE_LEAGUES),
            "ticket_window": "单日组单",
            "frequency": "每天最多一单, 已入选比赛不重复使用",
            "mixed_bet_policy": "平/让平混合有小幅加分",
        }
    low, high = PROFILE_ODDS_RANGE["balanced"]
    return {
        "strategy": strategy,
        "combo_odds_range": f"{low:g}-{high:g}",
        "excluded_leagues": sorted(NEGATIVE_LEAGUES),
        "ticket_window": "两天滚动组单",
        "frequency": "每个滚动窗口最多一单, 已入选比赛不重复使用",
        "mixed_bet_policy": "平/让平混合有加分",
    }


def _markdown_table(rows: list[dict[str, Any]], keys: list[str]) -> str:
    if not rows:
        return "无数据\n"
    lines = ["| " + " | ".join(keys) + " |", "| " + " | ".join("---" for _ in keys) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(key, "")) for key in keys) + " |")
    return "\n".join(lines) + "\n"


def _write_report(
    path: Path,
    *,
    summary: dict[str, Any],
    combo_rows: list[dict[str, Any]],
    random_rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = [
        "# V3.4 二串一组单选择器回测报告",
        "",
        "## 1. 摘要",
        _markdown_table([summary], sorted(summary)),
        "## 2. 策略表现",
        _markdown_table(
            combo_rows,
            [
                "strategy",
                "combo_count",
                "hit_count",
                "hit_rate",
                "roi",
                "avg_combo_odds",
                "coverage_rate",
                "max_losing_streak",
            ],
        ),
        "## 3. 随机对照",
        _markdown_table(
            random_rows,
            [
                "strategy",
                "label",
                "roi_avg",
                "roi_p80",
                "roi_p90",
                "roi_p95",
                "model_roi_percentile",
                "max_losing_streak_avg",
            ],
        ),
        "## 4. 结论提示",
        "- 本报告只优化组单选择器, 不改变 V3.2 单场候选规则。",
        "- 若策略没有超过约束随机 60% 分位, 不应进入生产推荐。",
    ]
    path.write_text("\n".join(content) + "\n", encoding="utf-8")


def _best_strategy_random_summary(
    random_rows: list[dict[str, Any]], *, strategy: str | None
) -> dict[str, Any]:
    if not strategy:
        return {}
    rows = [row for row in random_rows if row.get("strategy") == strategy]
    constrained = next((row for row in rows if row.get("label") == "候选池约束随机"), None)
    full_market = next((row for row in rows if row.get("label") == "全市场随机"), None)
    selected = constrained or full_market
    if not selected:
        return {}
    return {
        "random_label": selected.get("label"),
        "random_roi_avg": selected.get("roi_avg"),
        "model_roi_percentile_vs_random": selected.get("model_roi_percentile"),
        "full_market_random_roi_avg": full_market.get("roi_avg") if full_market else None,
        "full_market_model_roi_percentile": full_market.get("model_roi_percentile")
        if full_market
        else None,
        "constrained_random_roi_avg": constrained.get("roi_avg") if constrained else None,
        "constrained_model_roi_percentile": constrained.get("model_roi_percentile")
        if constrained
        else None,
    }


def _best_strategy_amount_summary(best: dict[str, Any]) -> dict[str, float]:
    combo_count = int(best.get("combo_count") or 0)
    stake = round(combo_count * STAKE_PER_TICKET, 4)
    pnl = round(float(best.get("pnl") or 0.0), 4)
    return {
        "best_strategy_stake": stake,
        "best_strategy_pnl": pnl,
        "best_strategy_return": round(stake + pnl, 4),
    }


def generate_combo_selector_report(
    db,
    *,
    model: str,
    start: date,
    end: date,
    random_trials: int = 1000,
    random_seed: int = 20260426,
    report_path: Path,
    tickets_csv: Path | None = None,
    random_csv: Path | None = None,
    replace: bool = False,
) -> ComboSelectorReportResult:
    tickets_csv = tickets_csv or report_path.with_name(f"{report_path.stem}-tickets.csv")
    random_csv = random_csv or report_path.with_name(f"{report_path.stem}-random.csv")

    model_config_id = get_model_config_id(db, model)
    if replace:
        replace_existing_run(db, name=RUN_NAME)
    candidates = load_model_candidates(db, model_config_id=model_config_id, start=start, end=end)
    if len(candidates) < 2:
        raise ValueError("Not enough candidates to build combo report")
    market_candidates = load_market_candidates(db, start=start, end=end)

    combo_rows: list[dict[str, Any]] = []
    random_rows: list[dict[str, Any]] = []
    ticket_rows: list[dict[str, Any]] = []
    ticket_payloads: list[tuple[str, dict[str, Any]]] = []
    random_ticket_payloads: list[tuple[str, dict[str, Any]]] = []
    total_days = _total_days(start, end)

    for idx, strategy in enumerate(STRATEGIES):
        tickets = select_combo_tickets(candidates, strategy=strategy)
        combo_summary = summarize_combo_tickets(tickets, total_days=total_days)
        combo_row = {"strategy": strategy, **combo_summary}
        combo_rows.append(combo_row)
        ticket_rows.extend(_ticket_row(strategy, ticket) for ticket in tickets)
        ticket_payloads.extend((strategy, _ticket_payload(strategy, ticket)) for ticket in tickets)

        for label, pool, seed_offset in (
            ("全市场随机", market_candidates, idx * 10),
            ("候选池约束随机", candidates, idx * 10 + 1),
        ):
            ticket_count = int(combo_summary["combo_count"])
            seed = random_seed + seed_offset
            random_rows.append(
                {
                    "strategy": strategy,
                    "label": label,
                    **run_random_combo_baseline(
                        pool,
                        ticket_count=ticket_count,
                        trials=random_trials,
                        seed=seed,
                        model_roi=float(combo_summary["roi"]),
                    ),
                }
            )
            random_ticket_payloads.extend(
                (
                    f"{strategy}:{label}",
                    _random_ticket_payload(strategy, label, ticket),
                )
                for ticket in sample_random_combo_tickets(
                    pool,
                    ticket_count=ticket_count,
                    seed=seed,
                )
            )

    best = max(combo_rows, key=lambda row: float(row["roi"]), default={})
    best_strategy = best.get("strategy")
    summary = {
        "model_name": model,
        "model_config_id": model_config_id,
        "date_from": str(start),
        "date_to": str(end),
        "candidates": len(candidates),
        "best_strategy": best_strategy,
        "best_strategy_roi": best.get("roi"),
        "best_strategy_combo_count": best.get("combo_count"),
        "strategy_rules": _strategy_rules(best_strategy),
        **_best_strategy_amount_summary(best),
        **_best_strategy_random_summary(random_rows, strategy=best_strategy),
    }
    _write_csv(tickets_csv, ticket_rows)
    _write_csv(random_csv, random_rows)
    _write_report(report_path, summary=summary, combo_rows=combo_rows, random_rows=random_rows)

    artifacts: list[tuple[str, str, dict[str, Any]]] = []
    artifacts.extend(("combo_simulation", row["strategy"], row) for row in combo_rows)
    artifacts.extend(
        ("random_baseline", f"{row['strategy']}:{row['label']}", row) for row in random_rows
    )
    artifacts.extend(("combo_ticket", strategy, payload) for strategy, payload in ticket_payloads)
    artifacts.extend(("random_ticket", label, payload) for label, payload in random_ticket_payloads)
    run = save_research_run(
        db,
        name=RUN_NAME,
        base_model_config_id=model_config_id,
        start=start,
        end=end,
        random_seed=random_seed,
        random_trials=random_trials,
        summary=summary,
        report_path=str(report_path),
        artifacts=artifacts,
    )
    return ComboSelectorReportResult(
        run_id=run.id,
        candidates=len(candidates),
        combo_summaries=len(combo_rows),
        random_baselines=len(random_rows),
        report_path=str(report_path),
        tickets_csv=str(tickets_csv),
        random_csv=str(random_csv),
        summary=summary,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V3.4 combo selector report")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--model", default="empirical-v32-filtered-candidate")
    parser.add_argument("--random-trials", type=int, default=1000)
    parser.add_argument("--random-seed", type=int, default=20260426)
    parser.add_argument(
        "--report",
        default="docs/analysis/2026-04-26-v34-combo-selector-backtest.md",
    )
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    start = _parse_date(args.start)
    end = _parse_date(args.end)
    report_path = Path(args.report)
    tickets_csv = report_path.with_name("v34-combo-selector-tickets.csv")
    random_csv = report_path.with_name("v34-combo-selector-random.csv")

    with SessionLocal() as db:
        result = generate_combo_selector_report(
            db,
            model=args.model,
            start=start,
            end=end,
            random_trials=args.random_trials,
            random_seed=args.random_seed,
            report_path=report_path,
            tickets_csv=tickets_csv,
            random_csv=random_csv,
            replace=args.replace,
        )
    print(
        f"run_id={result.run_id} candidates={result.candidates} "
        f"combo_summaries={result.combo_summaries} random_baselines={result.random_baselines}"
    )


if __name__ == "__main__":
    main()

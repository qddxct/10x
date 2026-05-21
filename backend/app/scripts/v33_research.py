"""Generate V3.3 research diagnostics for single factors and combo baselines."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from app.core.database import SessionLocal
from app.research.combo import simulate_combo_strategy, summarize_combo_tickets
from app.research.factors import build_factor_buckets
from app.research.random_baseline import run_random_combo_baseline
from app.research.reporting import write_v33_report
from app.research.repository import (
    V33_RUN_NAME,
    get_model_config_id,
    load_market_candidates,
    load_model_candidates,
    replace_existing_run,
    save_research_run,
)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _total_days(start: date, end: date) -> int:
    return (end - start).days + 1


def _combo_summary_row(strategy: str, candidates, *, start: date, end: date) -> dict:
    tickets = simulate_combo_strategy(candidates, strategy=strategy)  # type: ignore[arg-type]
    summary = summarize_combo_tickets(tickets, total_days=_total_days(start, end))
    return {"strategy": strategy, **summary}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V3.3 research report")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--model", default="empirical-v32-filtered-candidate")
    parser.add_argument("--random-trials", type=int, default=1000)
    parser.add_argument("--random-seed", type=int, default=20260426)
    parser.add_argument(
        "--report", default="docs/analysis/2026-04-26-v33-single-factor-and-combo-diagnostic.md"
    )
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    start = _parse_date(args.start)
    end = _parse_date(args.end)
    report_path = Path(args.report)
    bucket_csv = report_path.with_name("v33-single-factor-buckets.csv")
    combo_csv = report_path.with_name("v33-combo-simulation.csv")
    random_csv = report_path.with_name("v33-random-baseline.csv")

    with SessionLocal() as db:
        model_config_id = get_model_config_id(db, args.model)
        if args.replace:
            replace_existing_run(db, name=V33_RUN_NAME)
        candidates = load_model_candidates(
            db, model_config_id=model_config_id, start=start, end=end
        )
        market_candidates = load_market_candidates(db, start=start, end=end)

        factor_buckets = build_factor_buckets(candidates)
        combo_summaries = [
            _combo_summary_row("same_day_strongest", candidates, start=start, end=end),
            _combo_summary_row("two_day_rolling", candidates, start=start, end=end),
            _combo_summary_row("high_odds_attractor", candidates, start=start, end=end),
        ]
        model_roi = float(combo_summaries[0]["roi"]) if combo_summaries else 0.0
        ticket_count = int(combo_summaries[0]["combo_count"]) if combo_summaries else 0
        random_summaries = [
            {
                "label": "全市场随机",
                **run_random_combo_baseline(
                    market_candidates,
                    ticket_count=ticket_count,
                    trials=args.random_trials,
                    seed=args.random_seed,
                    model_roi=model_roi,
                ),
            },
            {
                "label": "约束随机",
                **run_random_combo_baseline(
                    candidates,
                    ticket_count=ticket_count,
                    trials=args.random_trials,
                    seed=args.random_seed + 1,
                    model_roi=model_roi,
                ),
            },
        ]
        summary = {
            "model_name": args.model,
            "model_config_id": model_config_id,
            "date_from": str(start),
            "date_to": str(end),
            "candidates": len(candidates),
            "market_candidates": len(market_candidates),
            "same_day_combo_count": ticket_count,
            "same_day_combo_roi": model_roi,
            "random_roi_avg": random_summaries[0]["roi_avg"],
            "model_roi_percentile_vs_random": random_summaries[0]["model_roi_percentile"],
        }
        write_v33_report(
            report_path=report_path,
            bucket_csv_path=bucket_csv,
            combo_csv_path=combo_csv,
            random_csv_path=random_csv,
            summary=summary,
            factor_buckets=factor_buckets,
            combo_summaries=combo_summaries,
            random_summaries=random_summaries,
        )
        artifacts = []
        artifacts.extend(
            ("factor_bucket", f"{row['factor']}:{row['label']}", row) for row in factor_buckets
        )
        artifacts.extend(("combo_simulation", row["strategy"], row) for row in combo_summaries)
        artifacts.extend(("random_baseline", row["label"], row) for row in random_summaries)
        run = save_research_run(
            db,
            name=V33_RUN_NAME,
            base_model_config_id=model_config_id,
            start=start,
            end=end,
            random_seed=args.random_seed,
            random_trials=args.random_trials,
            summary=summary,
            report_path=str(report_path),
            artifacts=artifacts,
        )
    print(
        f"run_id={run.id} candidates={len(candidates)} factor_buckets={len(factor_buckets)} "
        f"combo_summaries={len(combo_summaries)} random_baselines={len(random_summaries)}"
    )


if __name__ == "__main__":
    main()

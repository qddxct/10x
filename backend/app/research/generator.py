from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import ModelConfig
from app.scripts.v31_combination_candidate_backtest import generate_v32_scores
from app.scripts.v34_combo_selector import generate_combo_selector_report

DEFAULT_RESEARCH_MODEL = "empirical-v32-filtered-candidate"
GENERATED_REPORT_DIR = Path("docs/analysis/generated")


@dataclass(frozen=True)
class GeneratedResearchReport:
    run_id: int
    report_path: str
    score_summary: dict[str, int]
    research_summary: dict[str, Any]


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def generate_user_combo_report(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    model_name: str = DEFAULT_RESEARCH_MODEL,
    random_trials: int = 1000,
    random_seed: int = 20260426,
) -> GeneratedResearchReport:
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")
    if db.query(ModelConfig).filter(ModelConfig.name == model_name).one_or_none() is None:
        raise LookupError("ModelConfig not found")

    stamp = _timestamp()
    prefix = f"v34-combo-selector-{date_from.isoformat()}-{date_to.isoformat()}-{stamp}"
    score_result = generate_v32_scores(
        db,
        start=date_from,
        end=date_to,
        report_path=GENERATED_REPORT_DIR
        / f"v32-score-{date_from.isoformat()}-{date_to.isoformat()}-{stamp}.md",
        csv_path=GENERATED_REPORT_DIR
        / f"v32-score-{date_from.isoformat()}-{date_to.isoformat()}-{stamp}.csv",
        replace=True,
    )
    if score_result.rows == 0:
        raise ValueError("No finished matches in selected range")
    if score_result.recommended_scores < 2:
        raise ValueError("Not enough candidates to build combo report")

    report_result = generate_combo_selector_report(
        db,
        model=model_name,
        start=date_from,
        end=date_to,
        random_trials=random_trials,
        random_seed=random_seed,
        report_path=GENERATED_REPORT_DIR / f"{prefix}.md",
        replace=False,
    )
    return GeneratedResearchReport(
        run_id=report_result.run_id,
        report_path=report_result.report_path,
        score_summary={
            "rows": score_result.rows,
            "candidates": score_result.candidates,
            "portfolio": score_result.portfolio,
            "scored_matches": score_result.scored_matches,
            "recommended_scores": score_result.recommended_scores,
            "draw_scores": score_result.draw_scores,
            "handicap_draw_scores": score_result.handicap_draw_scores,
            "replaced_old_scores": score_result.replaced_old_scores,
        },
        research_summary=report_result.summary,
    )

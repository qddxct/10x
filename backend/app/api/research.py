from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.research.generator import generate_user_combo_report
from app.research.repository import (
    get_research_run,
    latest_research_run,
    research_artifacts_by_run,
    research_ticket_groups,
    research_tickets,
)
from app.schemas.research import (
    ResearchArtifactRead,
    ResearchGenerateRequest,
    ResearchGenerateResponse,
    ResearchRunDetailRead,
    ResearchRunRead,
    ResearchTicketGroupRead,
    ResearchTicketRead,
)

router = APIRouter()


@router.get("/latest", response_model=ResearchRunRead | None)
def get_latest_research_run(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ResearchRunRead | None:
    run = latest_research_run(db)
    return ResearchRunRead.model_validate(run) if run is not None else None


@router.post(
    "/generate-combo-report",
    response_model=ResearchGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_combo_report(
    payload: ResearchGenerateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ResearchGenerateResponse:
    try:
        result = generate_user_combo_report(
            db,
            date_from=payload.date_from,
            date_to=payload.date_to,
            model_name=payload.model_name,
            random_trials=payload.random_trials,
            random_seed=payload.random_seed,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ResearchGenerateResponse(
        run_id=result.run_id,
        report_path=result.report_path,
        score_summary=result.score_summary,
        research_summary=result.research_summary,
    )


@router.get("/{run_id}", response_model=ResearchRunDetailRead)
def get_research_run_detail(
    run_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ResearchRunDetailRead:
    run = get_research_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    grouped = {
        artifact_type: [ResearchArtifactRead.model_validate(row) for row in rows]
        for artifact_type, rows in research_artifacts_by_run(db, run.id).items()
    }
    base = ResearchRunRead.model_validate(run).model_dump()
    return ResearchRunDetailRead(**base, artifacts=grouped)


@router.get("/{run_id}/tickets", response_model=list[ResearchTicketRead])
def get_research_run_tickets(
    run_id: int,
    strategy: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ResearchTicketRead]:
    run = get_research_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    rows = research_tickets(db, run, strategy=strategy)
    return [ResearchTicketRead(**row.payload_json) for row in rows]


@router.get("/{run_id}/ticket-groups", response_model=list[ResearchTicketGroupRead])
def get_research_run_ticket_groups(
    run_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ResearchTicketGroupRead]:
    run = get_research_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    return [ResearchTicketGroupRead(**group) for group in research_ticket_groups(db, run)]


__all__ = ["router"]

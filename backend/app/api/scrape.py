from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import require_roles
from app.core.database import engine, get_db
from app.models.scrape_log import ScrapeLog
from app.models.user import User
from app.scheduler.jobs import JOB_REGISTRY
from app.schemas.scrape import (
    ScrapeJobInfo,
    ScrapeLogList,
    ScrapeLogOut,
    ScrapeRunResult,
)

router = APIRouter()

require_admin = require_roles("admin")

JOB_DESCRIPTIONS: dict[str, str] = {
    "schedule": "Sporttery 赛程抓取（每日 08:30）",  # noqa: RUF001
    "result": "Sporttery 赛果抓取（每日 23:30）",  # noqa: RUF001
    "odds": "Titan007 赔率抓取（每 2 小时）",  # noqa: RUF001
    "team_stats": "Sporttery 详情页球队状态抓取（每日 09:00）",  # noqa: RUF001
    "scoring": "模型评分批量计算（每日 09:15）",  # noqa: RUF001
}

JOB_LOG_NAMES: dict[str, tuple[str, ...]] = {
    "schedule": ("schedule", "sporttery_schedule", "titan007_odds", "titan007_analysis_stats"),
    "result": ("result", "sporttery_result"),
    "odds": ("odds", "titan007_odds"),
    "team_stats": ("team_stats", "sporttery_team_stats", "titan007_analysis_stats"),
    "scoring": ("scoring",),
}


def _session_factory_for_run() -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@router.get("/jobs", response_model=list[ScrapeJobInfo])
def list_jobs(
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
) -> list[ScrapeJobInfo]:
    jobs: list[ScrapeJobInfo] = []
    for name in JOB_REGISTRY:
        log_names = JOB_LOG_NAMES.get(name, (name,))
        last = (
            db.query(ScrapeLog)
            .filter(ScrapeLog.job_name.in_(log_names))
            .order_by(ScrapeLog.started_at.desc())
            .first()
        )
        jobs.append(
            ScrapeJobInfo(
                name=name,
                description=JOB_DESCRIPTIONS.get(name, ""),
                last_started_at=last.started_at if last is not None else None,
                last_finished_at=last.finished_at if last is not None else None,
                last_status=last.status if last is not None else None,
                last_records_count=last.records_count if last is not None else None,
            )
        )
    return jobs


@router.get("/logs", response_model=ScrapeLogList)
def list_logs(
    source: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    job_name: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
) -> ScrapeLogList:
    query = db.query(ScrapeLog)
    if source:
        query = query.filter(ScrapeLog.source == source)
    if status_filter:
        query = query.filter(ScrapeLog.status == status_filter)
    if job_name:
        query = query.filter(ScrapeLog.job_name == job_name)

    total = query.count()
    rows = query.order_by(ScrapeLog.started_at.desc()).offset(offset).limit(limit).all()
    return ScrapeLogList(
        items=[ScrapeLogOut.model_validate(r) for r in rows],
        total=total,
    )


@router.post(
    "/jobs/{name}/run",
    response_model=ScrapeRunResult,
    status_code=status.HTTP_200_OK,
)
def run_job_now(
    name: str,
    _user: User = Depends(require_admin),
) -> ScrapeRunResult:
    fn = JOB_REGISTRY.get(name)
    if fn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown job: {name}"
        )
    session_factory = _session_factory_for_run()
    outcome = fn(session_factory)
    return ScrapeRunResult(
        job=name,  # type: ignore[arg-type]
        status=outcome.status,
        records=outcome.records,
        error=outcome.error,
    )

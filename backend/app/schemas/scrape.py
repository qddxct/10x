from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ScrapeJobName = Literal["schedule", "result", "odds", "team_stats", "scoring"]
ScrapeStatus = Literal["running", "success", "failed", "partial"]
ScrapeSource = Literal["sporttery", "titan007", "other"]


class ScrapeLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: ScrapeSource
    job_name: str
    status: ScrapeStatus
    started_at: datetime
    finished_at: datetime | None
    records_count: int
    error_message: str | None


class ScrapeLogList(BaseModel):
    items: list[ScrapeLogOut]
    total: int


class ScrapeJobInfo(BaseModel):
    name: ScrapeJobName
    description: str
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_status: ScrapeStatus | None = None
    last_records_count: int | None = None


class ScrapeRunResult(BaseModel):
    job: ScrapeJobName
    status: ScrapeStatus
    records: int = Field(ge=0)
    error: str | None = None

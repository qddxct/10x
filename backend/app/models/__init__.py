from app.models.backtest import BacktestSession
from app.models.base import Base, TimestampMixin
from app.models.league import League
from app.models.match import SportteryMatch
from app.models.match_id import (
    build_logical_id,
    infer_business_date,
    logical_id_from_jc,
    logical_id_from_kickoff,
    parse_jc_code,
    split_logical_id,
    weekday_digit,
)
from app.models.model_config import ModelConfig
from app.models.odds import SportteryMatchOdds
from app.models.result import SportteryMatchResult
from app.models.research import ModelResearchArtifact, ModelResearchRun
from app.models.score import SportteryMatchScore
from app.models.scrape_log import ScrapeLog
from app.models.team_stats import SportteryMatchTeamStats
from app.models.user import User

# Backwards-compatible aliases for tests and older code paths that predate the
# sporttery_* table rename.
Match = SportteryMatch
MatchOdds = SportteryMatchOdds
MatchResult = SportteryMatchResult
MatchScore = SportteryMatchScore
MatchTeamStats = SportteryMatchTeamStats

__all__ = [
    "Base",
    "TimestampMixin",
    "BacktestSession",
    "League",
    "SportteryMatch",
    "SportteryMatchOdds",
    "SportteryMatchResult",
    "SportteryMatchScore",
    "SportteryMatchTeamStats",
    "Match",
    "MatchOdds",
    "MatchResult",
    "MatchScore",
    "MatchTeamStats",
    "ModelConfig",
    "ModelResearchRun",
    "ModelResearchArtifact",
    "ScrapeLog",
    "User",
    "build_logical_id",
    "infer_business_date",
    "logical_id_from_jc",
    "logical_id_from_kickoff",
    "parse_jc_code",
    "split_logical_id",
    "weekday_digit",
]

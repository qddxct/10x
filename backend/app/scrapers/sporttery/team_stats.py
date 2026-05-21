"""Sporttery team-stats scraper using 竞彩对阵详情 APIs."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

from sqlalchemy.orm import Session

from app.core.tz import now_beijing
from app.models.match import SportteryMatch
from app.models.team_stats import SportteryMatchTeamStats
from app.scrapers.base import ScrapeError, Scraper
from app.scrapers.http import build_client

logger = logging.getLogger(__name__)

HEAD_API = (
    "https://webapi.sporttery.cn/gateway/uniform/football/"
    "getMatchHeadV1.qry?source=web&sportteryMatchId={mid}"
)
H2H_API = (
    "https://webapi.sporttery.cn/gateway/uniform/football/"
    "getResultHistoryV1.qry?sportteryMatchId={mid}"
    "&termLimits=10&tournamentFlag=0&homeAwayFlag=0"
)
FORM_API = (
    "https://webapi.sporttery.cn/gateway/uniform/football/"
    "getMatchResultV1.qry?sportteryMatchId={mid}"
    "&termLimits=6&tournamentFlag=0&homeAwayFlag=0"
)


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


_RESULT_MAP = {"home": "W", "away": "L", "draw": "D"}


def _build_form(match_list: list[dict]) -> str | None:
    if not match_list:
        return None
    chars = [_RESULT_MAP.get(m.get("teamMatchResult", ""), "?") for m in match_list]
    return "".join(chars) or None


def _count_h2h(match_list: list[dict], our_home_team_id: int | None) -> dict:
    wins, draws, losses = 0, 0, 0
    if our_home_team_id is None:
        return {"h2h_home_wins": None, "h2h_draws": None, "h2h_away_wins": None}

    for m in match_list:
        winner = m.get("winningTeam")
        if winner == "draw":
            draws += 1
            continue

        h_id = m.get("sportteryHomeTeamId") or m.get("homeTeamId")
        a_id = m.get("sportteryAwayTeamId") or m.get("awayTeamId")

        if winner == "home":
            winning_team_id = h_id
        elif winner == "away":
            winning_team_id = a_id
        else:
            continue

        if winning_team_id == our_home_team_id:
            wins += 1
        else:
            losses += 1

    return {"h2h_home_wins": wins, "h2h_draws": draws, "h2h_away_wins": losses}


def fetch_stats_for_mid(mid: str) -> dict:
    """Fetch team stats from sporttery 竞彩对阵详情 APIs for a single match."""
    with build_client() as client:
        head_resp = client.get(HEAD_API.format(mid=mid))
        h2h_resp = client.get(H2H_API.format(mid=mid))
        form_resp = client.get(FORM_API.format(mid=mid))

    if head_resp.status_code != 200:
        raise ScrapeError(HEAD_API.format(mid=mid), head_resp.status_code, "non-200")
    if h2h_resp.status_code != 200:
        raise ScrapeError(H2H_API.format(mid=mid), h2h_resp.status_code, "non-200")
    if form_resp.status_code != 200:
        raise ScrapeError(FORM_API.format(mid=mid), form_resp.status_code, "non-200")

    head = head_resp.json().get("value", {}) or {}
    h2h = h2h_resp.json().get("value", {}) or {}
    form = form_resp.json().get("value", {}) or {}

    wbsj = head.get("wbsjStats", {}) or {}
    h_stats = wbsj.get("home", {}) or {}
    a_stats = wbsj.get("away", {}) or {}

    home_form_list = (form.get("home", {}) or {}).get("matchList", []) or []
    away_form_list = (form.get("away", {}) or {}).get("matchList", []) or []

    our_home_team_id = _safe_int(head.get("sportteryHomeTeamId"))
    h2h_list = (h2h.get("matchList", []) or [])

    return {
        "home_rank": _safe_int(h_stats.get("ranking")),
        "home_season_wins": _safe_int(h_stats.get("sWinGoalMatchCnt")),
        "home_season_draws": _safe_int(h_stats.get("sDrawMatchCnt")),
        "home_season_losses": _safe_int(h_stats.get("sLossGoalMatchCnt")),
        "home_home_wins": _safe_int(h_stats.get("sHomeWinGoalMatchCnt")),
        "home_home_draws": _safe_int(h_stats.get("sHomeDrawMatchCnt")),
        "home_home_losses": _safe_int(h_stats.get("sHomeLossGoalMatchCnt")),
        "home_recent_form": _build_form(home_form_list),
        "away_rank": _safe_int(a_stats.get("ranking")),
        "away_season_wins": _safe_int(a_stats.get("sWinGoalMatchCnt")),
        "away_season_draws": _safe_int(a_stats.get("sDrawMatchCnt")),
        "away_season_losses": _safe_int(a_stats.get("sLossGoalMatchCnt")),
        "away_away_wins": _safe_int(a_stats.get("sAwayWinGoalMatchCnt")),
        "away_away_draws": _safe_int(a_stats.get("sAwayDrawMatchCnt")),
        "away_away_losses": _safe_int(a_stats.get("sAwayLossGoalMatchCnt")),
        "away_recent_form": _build_form(away_form_list),
        **_count_h2h(h2h_list, our_home_team_id),
    }


Fetcher = Callable[[str], dict]


class SportteryTeamStats(Scraper):
    name = "sporttery_team_stats"
    source = "sporttery"

    def __init__(
        self,
        *,
        db: Session,
        match_ids: Iterable[str],
        fetcher: Fetcher | None = None,
    ):
        self._db = db
        self._match_ids = list(match_ids)
        self._fetcher = fetcher or fetch_stats_for_mid
        self._parsed: list[dict] = []

    def fetch(self) -> str:
        self._parsed = []
        for mid in self._match_ids:
            try:
                stats = self._fetcher(mid)
                self._parsed.append({"sporttery_match_id": mid, **stats})
            except Exception as exc:
                logger.warning("skip mid=%s: %s", mid, exc)
        return ""

    def parse(self, raw: str) -> list[dict]:
        return self._parsed

    def persist(self, rows: list[dict]) -> int:
        if not rows:
            return 0

        now = now_beijing()
        count = 0
        for row in rows:
            mid = row.pop("sporttery_match_id")
            match = (
                self._db.query(SportteryMatch)
                .filter(SportteryMatch.sporttery_match_id == mid)
                .one_or_none()
            )
            if match is None:
                logger.info("skip unknown match mid=%s", mid)
                continue

            existing = (
                self._db.query(SportteryMatchTeamStats)
                .filter(SportteryMatchTeamStats.match_id == match.id)
                .one_or_none()
            )
            fields = {**row, "scraped_at": now}
            if existing is None:
                self._db.add(SportteryMatchTeamStats(match_id=match.id, **fields))
            else:
                for k, v in fields.items():
                    setattr(existing, k, v)
            count += 1
        self._db.commit()
        return count

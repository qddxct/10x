"""Titan007 analysis-page team-stats scraper for upcoming recommendations.

This scraper fills ``sporttery_match_team_stats`` from Titan007
``analysis/{match_id}cn.htm`` pages. It is used by the normal schedule chain,
so upcoming recommendations have both real odds and pre-match analysis data.

Historical backfill uses the same analysis parser through ``scripts/backfill.py``;
Sporttery's team-stats APIs are intentionally not used here because they drift
when viewed after the match date.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.core.tz import now_beijing
from app.models.match import SportteryMatch
from app.models.team_stats import SportteryMatchTeamStats
from app.scrapers.base import ScrapeError, Scraper
from app.scrapers.http import build_client
from app.scrapers.titan007.analysis import TitanTeamStats, fetch_analysis, parse_analysis
from app.scrapers.titan007.history import JC_DEFAULT_HEADERS
from app.scrapers.titan007.odds import BF_JC_URL, _parse_bf_jc

logger = logging.getLogger(__name__)

MappingFetcher = Callable[[], dict[str, str]]
AnalysisFetcher = Callable[[str], str]
AnalysisParser = Callable[[str, str, str], TitanTeamStats | None]


def fetch_live_jc_to_titan_mapping() -> dict[str, str]:
    """Fetch Titan007 live feed and return ``{jc_code: titan_match_id}``."""
    with build_client() as client:
        response = client.get(BF_JC_URL, headers=JC_DEFAULT_HEADERS)
        if response.status_code != 200:
            raise ScrapeError(BF_JC_URL, response.status_code, "bf_jc.txt failed")
        text = response.content.decode("utf-8", errors="replace")

    tid_to_jc = _parse_bf_jc(text)
    return {jc_code: titan_id for titan_id, (jc_code, _kickoff) in tid_to_jc.items()}


class Titan007AnalysisStats(Scraper):
    """Upsert team stats for scheduled matches from Titan007 analysis pages."""

    name = "titan007_analysis_stats"
    source = "titan007"

    def __init__(
        self,
        *,
        db: Session,
        match_ids: Iterable[int],
        mapping_fetcher: MappingFetcher | None = None,
        analysis_fetcher: AnalysisFetcher | None = None,
        parser: AnalysisParser = parse_analysis,
    ) -> None:
        self._db = db
        self._match_ids = list(match_ids)
        self._mapping_fetcher = mapping_fetcher or fetch_live_jc_to_titan_mapping
        self._analysis_fetcher = analysis_fetcher
        self._parser = parser
        self._parsed: list[dict] = []

    def fetch(self) -> str:
        self._parsed = []
        if not self._match_ids:
            return ""

        jc_to_titan = self._mapping_fetcher()
        matches = (
            self._db.query(SportteryMatch)
            .filter(SportteryMatch.id.in_(self._match_ids))
            .order_by(SportteryMatch.id.asc())
            .all()
        )

        if self._analysis_fetcher is not None:
            for match in matches:
                self._fetch_one(match, jc_to_titan, self._analysis_fetcher)
            return ""

        with build_client(timeout=20) as client:
            for match in matches:
                self._fetch_one(
                    match,
                    jc_to_titan,
                    lambda titan_id: fetch_analysis(client, titan_id),
                )
        return ""

    def _fetch_one(
        self,
        match: SportteryMatch,
        jc_to_titan: dict[str, str],
        analysis_fetcher: AnalysisFetcher,
    ) -> None:
        jc_code = (match.round or "").strip()
        titan_match_id = jc_to_titan.get(jc_code)
        if titan_match_id is None:
            logger.info("skip match_id=%s: no titan007 mapping for %s", match.id, jc_code)
            return

        try:
            html = analysis_fetcher(titan_match_id)
            stats = self._parser(html, match.home_team, match.away_team)
        except Exception as exc:
            logger.warning(
                "skip titan analysis match_id=%s titan_id=%s: %s",
                match.id,
                titan_match_id,
                exc,
            )
            return

        if stats is None:
            logger.info(
                "skip titan analysis match_id=%s titan_id=%s: parse empty",
                match.id,
                titan_match_id,
            )
            return

        self._parsed.append({"match_id": match.id, **asdict(stats)})

    def parse(self, raw: str) -> list[dict]:
        return self._parsed

    def persist(self, rows: list[dict]) -> int:
        if not rows:
            return 0

        now = now_beijing()
        count = 0
        for row in rows:
            match_id = row["match_id"]
            fields = {k: v for k, v in row.items() if k != "match_id"}
            fields["scraped_at"] = now

            existing = (
                self._db.query(SportteryMatchTeamStats)
                .filter(SportteryMatchTeamStats.match_id == match_id)
                .one_or_none()
            )
            if existing is None:
                self._db.add(SportteryMatchTeamStats(match_id=match_id, **fields))
            else:
                for key, value in fields.items():
                    setattr(existing, key, value)
            count += 1

        self._db.commit()
        return count

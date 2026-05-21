"""Sporttery result scraper — getUniformMatchResultV1 API.

Fetches settled match results including full-time scores and
竞彩赔率 (HAD odds + HHAD goal line).  Odds are written directly
into ``sporttery_matches`` columns.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models.match import SportteryMatch
from app.models.result import SportteryMatchResult
from app.scrapers.base import ScrapeError, Scraper
from app.scrapers.http import build_client

logger = logging.getLogger(__name__)

RESULT_API_TEMPLATE = (
  "https://webapi.sporttery.cn/gateway/uniform/football/"
  "getUniformMatchResultV1.qry?"
  "matchBeginDate={begin}&matchEndDate={end}"
  "&leagueId=&pageSize=100&pageNo=1&isFix=0&matchPage=1&pcOrWap=1"
)

LOOKBACK_DAYS = 3


def _default_url() -> str:
  end = date.today()
  begin = end - timedelta(days=LOOKBACK_DAYS)
  return RESULT_API_TEMPLATE.format(
    begin=begin.isoformat(), end=end.isoformat()
  )


def _dec(v: str | None) -> Decimal | None:
  if not v:
    return None
  try:
    return Decimal(v)
  except InvalidOperation:
    return None


def _parse_score(score_str: str) -> tuple[int, int] | None:
  if not score_str or ':' not in score_str:
    return None
  parts = score_str.strip().split(':')
  if len(parts) != 2:
    return None
  try:
    return int(parts[0].strip()), int(parts[1].strip())
  except ValueError:
    return None


def _classify(home: int, away: int) -> str:
  if home > away:
    return 'home_win'
  if home < away:
    return 'away_win'
  return 'draw'


class SportteryResult(Scraper):
  name = 'sporttery_result'
  source = 'sporttery'

  def __init__(self, *, db: Session, raw: str | None = None, url: str | None = None):
    self._db = db
    self._raw = raw
    self._url = url or _default_url()

  def fetch(self) -> str:
    if self._raw is not None:
      return self._raw
    with build_client() as client:
      resp = client.get(self._url)
      if resp.status_code != 200:
        raise ScrapeError(self._url, resp.status_code, 'non-200 response')
      return resp.text

  def parse(self, raw: str) -> list[dict]:
    try:
      payload = json.loads(raw)
    except json.JSONDecodeError as err:
      raise ScrapeError(self._url, None, f'invalid JSON: {err}') from err

    if not payload.get('success'):
      raise ScrapeError(
        self._url, None, payload.get('errorMessage', 'API returned failure')
      )

    value = payload.get('value') or {}
    match_list = value.get('matchResult') or []
    rows: list[dict] = []

    for m in match_list:
      if str(m.get('matchResultStatus', '')) != '2':
        continue

      mid = str(m.get('matchId', ''))
      if not mid:
        continue

      score_str = m.get('sectionsNo999') or ''
      parsed = _parse_score(score_str)
      if parsed is None:
        logger.debug('no score for mid=%s sectionsNo999=%r', mid, score_str)
        continue

      rows.append({
        'sporttery_match_id': mid,
        'home_score': parsed[0],
        'away_score': parsed[1],
        'had_h': _dec(m.get('h')),
        'had_d': _dec(m.get('d')),
        'had_a': _dec(m.get('a')),
        'hhad_goal_line': _dec(m.get('goalLine')),
      })

    return rows

  def persist(self, rows: list[dict]) -> int:
    if not rows:
      return 0

    count = 0
    for row in rows:
      match = (
        self._db.query(SportteryMatch)
        .filter(SportteryMatch.sporttery_match_id == row['sporttery_match_id'])
        .one_or_none()
      )
      if match is None:
        logger.info('skip unknown match %s', row['sporttery_match_id'])
        continue

      result = (
        self._db.query(SportteryMatchResult)
        .filter(SportteryMatchResult.match_id == match.id)
        .one_or_none()
      )
      outcome = _classify(row['home_score'], row['away_score'])
      if result is None:
        result = SportteryMatchResult(
          match_id=match.id,
          home_score=row['home_score'],
          away_score=row['away_score'],
          result=outcome,
        )
        self._db.add(result)
      else:
        result.home_score = row['home_score']
        result.away_score = row['away_score']
        result.result = outcome

      if row['had_h'] is not None:
        match.had_h = row['had_h']
      if row['had_d'] is not None:
        match.had_d = row['had_d']
      if row['had_a'] is not None:
        match.had_a = row['had_a']
      if row['hhad_goal_line'] is not None:
        match.hhad_goal_line = row['hhad_goal_line']

      match.status = 'finished'
      count += 1

    self._db.commit()
    return count

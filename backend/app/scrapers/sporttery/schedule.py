"""Sporttery schedule scraper — getMatchCalculatorV1 API.

Uses the calculator API which returns match list together with
竞彩赔率 (HAD / HHAD odds) inline.  Odds are saved directly into
``sporttery_matches`` columns — NOT into ``sporttery_match_odds``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models.league import League
from app.models.match import SportteryMatch
from app.models.match_id import logical_id_from_kickoff
from app.scrapers.base import ScrapeError, Scraper
from app.scrapers.http import build_client

logger = logging.getLogger(__name__)

SCHEDULE_API = (
  "https://webapi.sporttery.cn/gateway/uniform/football/"
  "getMatchCalculatorV1.qry?channel=c&poolCode=hhad,had"
)


def _dec(v: str | None) -> Decimal | None:
  if not v:
    return None
  try:
    return Decimal(v)
  except InvalidOperation:
    return None


def parse_schedule_api(payload: dict) -> list[dict]:
  """Parse the calculator API response into a flat list of match dicts."""
  value = payload.get('value') or {}
  date_groups = value.get('matchInfoList') or []
  rows: list[dict] = []

  for group in date_groups:
    for m in group.get('subMatchList') or []:
      mid = m.get('matchId')
      if not mid:
        continue

      home = m.get('homeTeamAbbName') or ''
      away = m.get('awayTeamAbbName') or ''
      league = m.get('leagueAbbName') or ''
      match_code = m.get('matchNumStr') or ''
      match_date_str = m.get('matchDate') or ''
      match_time_str = m.get('matchTime') or ''

      if not (home and away and league and match_date_str):
        continue

      try:
        kickoff = datetime.strptime(
          f'{match_date_str} {match_time_str}', '%Y-%m-%d %H:%M:%S'
        )
      except ValueError:
        logger.warning('bad kickoff %s %s', match_date_str, match_time_str)
        continue

      had = m.get('had') or {}
      hhad = m.get('hhad') or {}

      rows.append({
        'sporttery_match_id': str(mid),
        'match_code': match_code,
        'league_name': league,
        'home_team': home,
        'away_team': away,
        'match_date': kickoff,
        'had_h': _dec(had.get('h')),
        'had_d': _dec(had.get('d')),
        'had_a': _dec(had.get('a')),
        'hhad_h': _dec(hhad.get('h')),
        'hhad_d': _dec(hhad.get('d')),
        'hhad_a': _dec(hhad.get('a')),
        'hhad_goal_line': _dec(hhad.get('goalLine')),
      })

  return rows


class SportterySchedule(Scraper):
  name = 'sporttery_schedule'
  source = 'sporttery'

  def __init__(self, *, db: Session, raw: str | None = None, url: str = SCHEDULE_API):
    self._db = db
    self._raw = raw
    self._url = url

  def fetch(self) -> str:
    if self._raw is not None:
      return self._raw
    with build_client() as client:
      resp = client.get(self._url)
      if resp.status_code != 200:
        raise ScrapeError(self._url, resp.status_code, 'non-200 response')
      return resp.text

  def parse(self, raw: str) -> list[dict]:
    import json

    try:
      payload = json.loads(raw)
    except json.JSONDecodeError as err:
      raise ScrapeError(self._url, None, f'invalid JSON: {err}') from err

    if not payload.get('success'):
      raise ScrapeError(
        self._url, None, payload.get('errorMessage', 'API returned failure')
      )
    return parse_schedule_api(payload)

  def persist(self, rows: list[dict]) -> int:
    if not rows:
      return 0

    league_cache: dict[str, League] = {}
    count = 0

    for row in rows:
      match_code = row.get('match_code') or ''
      logical_id = logical_id_from_kickoff(row['match_date'], match_code)
      if logical_id is None:
        logger.warning(
          'skip match %s: bad match_code=%s',
          row.get('sporttery_match_id'), match_code,
        )
        continue

      league = self._get_or_create_league(league_cache, row['league_name'])
      match = self._db.get(SportteryMatch, logical_id)

      if match is None:
        match = SportteryMatch(
          id=logical_id,
          league_id=league.id,
          sporttery_match_id=row['sporttery_match_id'],
          home_team=row['home_team'],
          away_team=row['away_team'],
          match_date=row['match_date'],
          round=match_code,
          status='scheduled',
          had_h=row['had_h'],
          had_d=row['had_d'],
          had_a=row['had_a'],
          hhad_h=row['hhad_h'],
          hhad_d=row['hhad_d'],
          hhad_a=row['hhad_a'],
          hhad_goal_line=row['hhad_goal_line'],
        )
        self._db.add(match)
        self._db.flush()
      else:
        match.league_id = league.id
        match.sporttery_match_id = row['sporttery_match_id']
        match.home_team = row['home_team']
        match.away_team = row['away_team']
        match.match_date = row['match_date']
        match.round = match_code
        match.had_h = row['had_h']
        match.had_d = row['had_d']
        match.had_a = row['had_a']
        match.hhad_h = row['hhad_h']
        match.hhad_d = row['hhad_d']
        match.hhad_a = row['hhad_a']
        match.hhad_goal_line = row['hhad_goal_line']

      count += 1

    self._db.commit()
    return count

  def _get_or_create_league(self, cache: dict[str, League], name: str) -> League:
    if name in cache:
      return cache[name]
    league = self._db.query(League).filter(League.name == name).one_or_none()
    if league is None:
      league = League(name=name)
      self._db.add(league)
      self._db.flush()
    cache[name] = league
    return league

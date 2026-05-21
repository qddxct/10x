"""Titan007 Bet365 odds scraper via real-time XML feeds.

Uses two lightweight text feeds from jc.titan007.com:

- ``xml/bf_jc.txt``       → match list with titan007_id + jc_code mapping
- ``xml/goallottery1.txt`` → Bet365 (cid=1) 欧赔 + 亚盘 for ALL live matches

These feeds cover **all** currently-selling matches in a single request,
unlike ``oddsData.aspx`` which is date-based and has delayed coverage.

For historical backfill, the date-based ``oddsData.aspx`` API is still
used by :mod:`app.scripts.backfill`.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.match import SportteryMatch
from app.models.match_id import logical_id_from_kickoff, parse_jc_code
from app.models.odds import SportteryMatchOdds
from app.core.tz import now_beijing
from app.scrapers.base import ScrapeError, Scraper
from app.scrapers.http import build_client
from app.scrapers.titan007.history import (
  JC_DEFAULT_HEADERS,
  parse_odds_data,
)

logger = logging.getLogger(__name__)

BF_JC_URL = 'https://jc.titan007.com/xml/bf_jc.txt'
ODDS_TXT_URL = 'https://jc.titan007.com/xml/goallottery1.txt'


def _dec(v: str | None) -> Decimal | None:
  if not v:
    return None
  try:
    return Decimal(v)
  except InvalidOperation:
    return None


def _parse_ts(value: str) -> datetime | None:
  if not value:
    return None
  parts = value.split(',')
  if len(parts) != 6:
    return None
  try:
    y, m, d, h, mi, s = (int(p) for p in parts)
    return datetime(y, m + 1, d, h, mi, s)
  except (ValueError, TypeError):
    return None


def _parse_bf_jc(text: str) -> dict[str, tuple[str, datetime | None]]:
  """Parse bf_jc.txt → {titan007_match_id: (jc_code, kickoff)}."""
  if not text:
    return {}
  sections = text.split('$')
  if len(sections) < 2:
    return {}
  mapping: dict[str, tuple[str, datetime | None]] = {}
  for row in sections[1:]:
    if not row:
      continue
    for match_block in row.split('!'):
      if not match_block:
        continue
      fields = match_block.split('^')
      if len(fields) < 5:
        continue
      match_id = fields[0].strip()
      jc_code = fields[4].strip()
      kickoff = _parse_ts(fields[1]) if len(fields) > 1 else None
      if match_id and jc_code and parse_jc_code(jc_code) is not None:
        mapping[match_id] = (jc_code, kickoff)
  return mapping


class Titan007Odds(Scraper):
  name = 'titan007_odds'
  source = 'titan007'

  def __init__(self, *, db: Session):
    self._db = db
    self._bf_text = ''
    self._odds_text = ''

  def fetch(self) -> str:
    with build_client() as client:
      r1 = client.get(BF_JC_URL, headers=JC_DEFAULT_HEADERS)
      if r1.status_code != 200:
        raise ScrapeError(BF_JC_URL, r1.status_code, 'bf_jc.txt failed')

      r2 = client.get(ODDS_TXT_URL, headers=JC_DEFAULT_HEADERS)
      if r2.status_code != 200:
        raise ScrapeError(ODDS_TXT_URL, r2.status_code, 'goallottery1.txt failed')

    self._bf_text = r1.content.decode('utf-8', errors='replace')
    self._odds_text = r2.content.decode('utf-8', errors='replace')
    return self._odds_text

  def parse(self, raw: str) -> list[dict]:
    tid_to_jc = _parse_bf_jc(self._bf_text)
    odds_list = parse_odds_data(raw)
    odds_by_tid = {o.match_id: o for o in odds_list}

    rows = []
    for tid, (jc_code, kickoff) in tid_to_jc.items():
      o = odds_by_tid.get(tid)
      if o is None:
        continue
      if kickoff is None:
        continue
      logical_id = logical_id_from_kickoff(kickoff, jc_code)
      if logical_id is None:
        continue
      rows.append({
        'logical_id': logical_id,
        'match_code': jc_code,
        'win_odds': o.win_odds,
        'draw_odds': o.draw_odds,
        'lose_odds': o.lose_odds,
        'handicap_value': o.handicap_value,
        'asian_handicap': str(o.handicap_value) if o.handicap_value is not None else None,
        'win_handicap_odds': o.win_handicap_odds,
        'draw_handicap_odds': None,
        'lose_handicap_odds': o.lose_handicap_odds,
        'total_goals': None,
      })
    logger.info('titan007 live odds: %d jc_matches, %d odds, %d matched',
                len(tid_to_jc), len(odds_list), len(rows))
    return rows

  def persist(self, rows: list[dict]) -> int:
    if not rows:
      return 0

    now = now_beijing()
    count = 0
    for row in rows:
      match = self._db.get(SportteryMatch, row['logical_id'])
      if match is None:
        continue

      odds = (
        self._db.query(SportteryMatchOdds)
        .filter(
          SportteryMatchOdds.match_id == match.id,
          SportteryMatchOdds.source == 'titan007',
        )
        .one_or_none()
      )
      fields = {
        'win_odds': row['win_odds'],
        'draw_odds': row['draw_odds'],
        'lose_odds': row['lose_odds'],
        'asian_handicap': row['asian_handicap'],
        'handicap_value': row['handicap_value'],
        'win_handicap_odds': row['win_handicap_odds'],
        'draw_handicap_odds': row['draw_handicap_odds'],
        'lose_handicap_odds': row['lose_handicap_odds'],
        'total_goals': row['total_goals'],
        'scraped_at': now,
      }
      if odds is None:
        odds = SportteryMatchOdds(match_id=match.id, source='titan007', **fields)
        self._db.add(odds)
      else:
        for k, v in fields.items():
          setattr(odds, k, v)
      count += 1
    self._db.commit()
    return count

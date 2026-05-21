"""Historical data backfill with explicit source boundaries.

For each date in a range:

1. Fetch ``getUniformMatchResultV1.qry`` from Sporttery → match list + scores + 竞彩赔率.
2. Fetch ``JcResult.aspx`` from Titan007 → jc_code → titan007_match_id mapping.
3. Fetch ``oddsData.aspx`` from Titan007 → real European odds.
4. Optionally fetch Titan007 ``analysis/{match_id}cn.htm`` pages for historical
   team stats.

Important: historical team stats must not use Sporttery's team-stats APIs.
Those APIs can show the latest team state when viewed after the match date,
which leaks future information into model research and backtests.

Supports day-by-day resume via the ``scrape_logs`` table — a day with a
previous ``success`` entry for ``sporttery_backfill`` is skipped unless ``--force``.

Usage (inside backend container)::

    docker exec -e PYTHONPATH=/app -w /app sporttery_backend \
        python -m app.scripts.backfill --from 2025-04-22 --to 2026-04-22

    # Re-run a single date, ignoring prior log:
    python -m app.scripts.backfill --from 2026-04-20 --to 2026-04-20 --force
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.tz import now_beijing
from app.models.league import League
from app.models.match import SportteryMatch
from app.models.match_id import build_logical_id, parse_jc_code
from app.models.odds import SportteryMatchOdds
from app.models.result import SportteryMatchResult
from app.models.scrape_log import ScrapeLog
from app.models.team_stats import SportteryMatchTeamStats
from app.scrapers.http import build_client
from app.scrapers.titan007.analysis import fetch_analysis, parse_analysis
from app.scrapers.titan007.history import (
  JC_DEFAULT_HEADERS,
  JC_RESULT_URL,
  ODDS_DATA_URL,
  ODDSLIST_JS_URL,
  TITAN_HKJC_COMPANY_ID,
  TitanLeague,
  TitanMatch,
  TitanOdds,
  merge_titan_odds_by_priority,
  parse_jc_result,
  parse_odds_data,
  parse_oddslist_js_company,
)

logger = logging.getLogger(__name__)

SCRAPER_NAME = 'sporttery_backfill'
TITAN_RECENT_SCORE_FIELDS = (
  'home_recent_matches_count',
  'home_recent_goals_for',
  'home_recent_goals_against',
  'home_recent_goal_diff',
  'home_recent_win_by_1',
  'home_recent_win_by_2plus',
  'home_recent_loss_by_1',
  'home_recent_loss_by_2plus',
  'home_recent_draw_score_count',
  'home_recent_low_scoring_count',
  'home_recent_high_scoring_count',
  'away_recent_matches_count',
  'away_recent_goals_for',
  'away_recent_goals_against',
  'away_recent_goal_diff',
  'away_recent_win_by_1',
  'away_recent_win_by_2plus',
  'away_recent_loss_by_1',
  'away_recent_loss_by_2plus',
  'away_recent_draw_score_count',
  'away_recent_low_scoring_count',
  'away_recent_high_scoring_count',
  'home_home_recent_matches_count',
  'home_home_recent_goals_for',
  'home_home_recent_goals_against',
  'home_home_recent_goal_diff',
  'home_home_recent_win_by_1',
  'home_home_recent_win_by_2plus',
  'home_home_recent_loss_by_1',
  'home_home_recent_loss_by_2plus',
  'away_away_recent_matches_count',
  'away_away_recent_goals_for',
  'away_away_recent_goals_against',
  'away_away_recent_goal_diff',
  'away_away_recent_win_by_1',
  'away_away_recent_win_by_2plus',
  'away_away_recent_loss_by_1',
  'away_away_recent_loss_by_2plus',
  'h2h_matches_count',
  'h2h_home_goals_for',
  'h2h_home_goals_against',
  'h2h_goal_diff',
  'h2h_draw_score_count',
  'h2h_one_goal_margin_count',
  'h2h_low_scoring_count',
  'h2h_high_scoring_count',
)

SPORTTERY_RESULT_URL = (
  'https://webapi.sporttery.cn/gateway/uniform/football/'
  'getUniformMatchResultV1.qry'
)
SPORTTERY_HEADERS = {
  'Referer': 'https://www.sporttery.cn/jc/zqsgkj/',
}
FIXED_BONUS_URL = (
  'https://webapi.sporttery.cn/gateway/uniform/football/'
  'getFixedBonusV1.qry?clientCode=3001&matchId={mid}'
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dec(v):
  if not v:
    return None
  try:
    return Decimal(v)
  except InvalidOperation:
    return None


def _parse_score(s):
  if not s or ':' not in s:
    return None, None
  parts = s.split(':')
  try:
    return int(parts[0]), int(parts[1])
  except (ValueError, IndexError):
    return None, None


def _classify_result(home: int, away: int) -> str:
  if home > away:
    return 'home_win'
  if home < away:
    return 'away_win'
  return 'draw'


def _classify_handicap(
  home: int, away: int, handicap: Decimal | None
) -> str | None:
  if handicap is None:
    return None
  adjusted = (Decimal(home) + handicap) - Decimal(away)
  if adjusted > 0:
    return 'home_win'
  if adjusted < 0:
    return 'away_win'
  return 'draw'


def daterange(start: date, end: date):
  current = start
  while current <= end:
    yield current
    current += timedelta(days=1)


def already_synced(db: Session, target: date) -> bool:
  start = datetime.combine(target, datetime.min.time())
  end = start + timedelta(days=1)
  return (
    db.query(SportteryMatch)
    .filter(SportteryMatch.match_date >= start, SportteryMatch.match_date < end)
    .first()
    is not None
  )


# ---------------------------------------------------------------------------
# Fetch layer
# ---------------------------------------------------------------------------

def fetch_sporttery_day(client: httpx.Client, target_date: date) -> list[dict]:
  """Fetch all pages of Sporttery results for *target_date*."""
  date_str = target_date.isoformat()
  all_rows: list[dict] = []
  page = 1

  while True:
    resp = client.get(
      SPORTTERY_RESULT_URL,
      params={
        'matchBeginDate': date_str,
        'matchEndDate': date_str,
        'leagueId': '',
        'pageSize': '100',
        'pageNo': str(page),
        'isFix': '0',
        'matchPage': '1',
        'pcOrWap': '1',
      },
      headers=SPORTTERY_HEADERS,
    )
    if resp.status_code != 200:
      raise httpx.HTTPStatusError(
        f'Sporttery HTTP {resp.status_code}',
        request=resp.request, response=resp,
      )
    body = resp.json()
    value = body.get('value') or {}
    rows = value.get('matchResult') or []
    all_rows.extend(rows)

    total_pages = int(value.get('pages', 1) or 1)
    if page >= total_pages:
      break
    page += 1

  return all_rows


def fetch_titan_day(
  client: httpx.Client, target_date: date
) -> tuple[list[TitanLeague], list[TitanMatch], list[TitanOdds]]:
  """Fetch JcResult + Macau oddsData, with HKJC single-match fallback."""
  date_str = target_date.isoformat()

  r1 = client.get(f'{JC_RESULT_URL}?d={date_str}', headers=JC_DEFAULT_HEADERS)
  if r1.status_code != 200:
    raise httpx.HTTPStatusError(
      f'JcResult HTTP {r1.status_code}',
      request=r1.request, response=r1,
    )
  leagues, matches = parse_jc_result(r1.content.decode('utf-8', errors='replace'))

  odds = fetch_titan_odds_with_fallback(client, target_date, matches)

  return leagues, matches, odds


def fetch_titan_odds_with_fallback(
  client: httpx.Client, target_date: date, matches: list[TitanMatch]
) -> list[TitanOdds]:
  """Fetch Macau odds first, then fill missing matches from HKJC.

  Macau cid=1 remains the primary source. HKJC company id 432 is read from the
  single-match 1x2 JS only for match ids missing from Macau.
  """
  date_str = target_date.isoformat()
  response = client.get(
    f'{ODDS_DATA_URL}?d={date_str}&cid=1&st=1',
    headers=JC_DEFAULT_HEADERS,
  )
  if response.status_code != 200:
    raise httpx.HTTPStatusError(
      f'oddsData macau HTTP {response.status_code}',
      request=response.request,
      response=response,
    )

  macau_odds = parse_odds_data(response.content.decode('utf-8', errors='replace'))
  macau_odds_by_match_id = {item.match_id: item for item in macau_odds}
  missing_match_ids = [
    item.match_id
    for item in matches
    if item.jc_code and _needs_hkjc_euro_fallback(macau_odds_by_match_id.get(item.match_id))
  ]

  hkjc_odds: list[TitanOdds] = []
  for match_id in missing_match_ids:
    try:
      fallback = client.get(
        ODDSLIST_JS_URL.format(match_id=match_id),
        headers={
          **JC_DEFAULT_HEADERS,
          'Referer': f'https://1x2.titan007.com/oddslist/{match_id}.htm',
        },
      )
    except Exception as err:
      logger.info(
        'skip hkjc fallback odds date=%s match_id=%s error=%s',
        date_str,
        match_id,
        err,
      )
      continue
    if fallback.status_code != 200:
      logger.info(
        'skip hkjc fallback odds date=%s match_id=%s status=%s',
        date_str,
        match_id,
        fallback.status_code,
      )
      continue
    parsed = parse_oddslist_js_company(
      match_id,
      fallback.content.decode('utf-8-sig', errors='replace'),
      TITAN_HKJC_COMPANY_ID,
    )
    if parsed is not None:
      hkjc_odds.append(parsed)

  return merge_titan_odds_by_priority([macau_odds, hkjc_odds])


def _needs_hkjc_euro_fallback(odds: TitanOdds | None) -> bool:
  """HKJC fallback is needed when Macau has no row or no complete euro odds."""
  if odds is None:
    return True
  return odds.win_odds is None or odds.draw_odds is None or odds.lose_odds is None


def fetch_day(client: httpx.Client, target: date):
  """Fetch both Sporttery and Titan007 data for a single date."""
  sporttery_rows = fetch_sporttery_day(client, target)
  _, titan_matches, titan_odds = fetch_titan_day(client, target)
  return sporttery_rows, titan_matches, titan_odds


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_or_create_league(
  db: Session, cache: dict[str, League], name: str
) -> League:
  cached = cache.get(name)
  if cached is not None:
    return cached
  league = db.query(League).filter(League.name == name).one_or_none()
  if league is None:
    league = League(name=name)
    db.add(league)
    db.flush()
  cache[name] = league
  return league


def _fetch_hhad_odds(client: httpx.Client, sporttery_match_id: str) -> dict | None:
  """Fetch closing HHAD odds from getFixedBonusV1.qry."""
  try:
    resp = client.get(
      FIXED_BONUS_URL.format(mid=sporttery_match_id),
      headers=SPORTTERY_HEADERS,
    )
    if resp.status_code != 200:
      return None
    body = resp.json()
    hhad_list = (body.get('value') or {}).get('oddsHistory', {}).get('hhadList') or []
    if not hhad_list:
      return None
    closing = hhad_list[-1]
    return {
      'hhad_h': _dec(closing.get('h')),
      'hhad_d': _dec(closing.get('d')),
      'hhad_a': _dec(closing.get('a')),
    }
  except Exception as err:
    logger.debug('hhad fetch failed mid=%s: %s', sporttery_match_id, err)
    return None


def _upsert_team_stats(
  db: Session,
  match: SportteryMatch,
  titan_match_id: str,
  client: httpx.Client,
  *,
  delay: float = 0.5,
) -> bool:
  """Fetch Titan007 analysis page and upsert historical stats for one match.

  Returns True if a row was written/updated.
  """
  try:
    html = fetch_analysis(client, titan_match_id)
    parsed = parse_analysis(html, match.home_team, match.away_team)
  except Exception as err:
    logger.debug('team_stats fetch failed titan_id=%s: %s', titan_match_id, err)
    return False

  if parsed is None:
    logger.debug('team_stats parse failed titan_id=%s', titan_match_id)
    return False

  now = now_beijing()
  existing = (
    db.query(SportteryMatchTeamStats)
    .filter(SportteryMatchTeamStats.match_id == match.id)
    .one_or_none()
  )
  fields = {
    'home_rank': parsed.home_rank,
    'home_season_wins': parsed.home_season_wins,
    'home_season_draws': parsed.home_season_draws,
    'home_season_losses': parsed.home_season_losses,
    'home_home_wins': parsed.home_home_wins,
    'home_home_draws': parsed.home_home_draws,
    'home_home_losses': parsed.home_home_losses,
    'home_recent_form': parsed.home_recent_form,
    'away_rank': parsed.away_rank,
    'away_season_wins': parsed.away_season_wins,
    'away_season_draws': parsed.away_season_draws,
    'away_season_losses': parsed.away_season_losses,
    'away_away_wins': parsed.away_away_wins,
    'away_away_draws': parsed.away_away_draws,
    'away_away_losses': parsed.away_away_losses,
    'away_recent_form': parsed.away_recent_form,
    'h2h_home_wins': parsed.h2h_home_wins,
    'h2h_draws': parsed.h2h_draws,
    'h2h_away_wins': parsed.h2h_away_wins,
    'scraped_at': now,
  }
  fields.update({
    key: getattr(parsed, key)
    for key in TITAN_RECENT_SCORE_FIELDS
  })
  if existing is None:
    db.add(SportteryMatchTeamStats(match_id=match.id, **fields))
  else:
    for key, value in fields.items():
      setattr(existing, key, value)
  if delay > 0:
    time.sleep(delay)
  return True


# ---------------------------------------------------------------------------
# Core upsert
# ---------------------------------------------------------------------------

def upsert_day(
  db: Session,
  business_date: date,
  sporttery_rows: list[dict],
  titan_matches: list[TitanMatch],
  titan_odds: list[TitanOdds],
  *,
  client: httpx.Client | None = None,
  fetch_team_stats: bool = True,
  stats_delay: float = 0.5,
) -> dict:
  """Upsert all data for a single 竞彩 business date. Returns stats dict."""

  jc_to_titan: dict[str, str] = {
    tm.jc_code: tm.match_id for tm in titan_matches if tm.jc_code
  }
  odds_by_tid: dict[str, TitanOdds] = {o.match_id: o for o in titan_odds}

  league_cache: dict[str, League] = {}
  hhad_queue: list[tuple[SportteryMatch, str]] = []
  stats_queue: list[tuple[SportteryMatch, str]] = []
  stats = {
    'matches': 0,
    'matches_new': 0,
    'results': 0,
    'odds': 0,
    'team_stats': 0,
    'hhad': 0,
    'skipped_bad_jc_code': 0,
  }

  now = now_beijing()

  for row in sporttery_rows:
    match_num_str = (row.get('matchNumStr') or '').strip()
    if not match_num_str:
      stats['skipped_bad_jc_code'] += 1
      continue

    parsed = parse_jc_code(match_num_str)
    if parsed is None:
      stats['skipped_bad_jc_code'] += 1
      logger.debug('skip bad matchNumStr=%s', match_num_str)
      continue

    weekday, seq = parsed
    try:
      logical_id = build_logical_id(business_date, weekday, seq)
    except ValueError as err:
      stats['skipped_bad_jc_code'] += 1
      logger.debug(
        'skip matchNumStr=%s on %s: %s', match_num_str, business_date, err,
      )
      continue

    league_name = (row.get('leagueNameAbbr') or 'unknown').strip() or 'unknown'
    league = _get_or_create_league(db, league_cache, league_name)

    sporttery_mid = str(row.get('matchId', '')) or None
    home_team = (row.get('homeTeam') or '').strip()
    away_team = (row.get('awayTeam') or '').strip()
    match_date_str = row.get('matchDate') or business_date.isoformat()
    is_finished = str(row.get('matchResultStatus', '')) == '2'

    had_h = _dec(row.get('h'))
    had_d = _dec(row.get('d'))
    had_a = _dec(row.get('a'))
    hhad_goal_line = _dec(row.get('goalLine'))

    match = db.get(SportteryMatch, logical_id)
    if match is None:
      match_date = (
        datetime.fromisoformat(match_date_str)
        if 'T' in match_date_str
        else datetime.strptime(match_date_str, '%Y-%m-%d')
      )
      match = SportteryMatch(
        id=logical_id,
        league_id=league.id,
        sporttery_match_id=sporttery_mid,
        home_team=home_team,
        away_team=away_team,
        match_date=match_date,
        round=match_num_str,
        status='finished' if is_finished else 'scheduled',
        had_h=had_h,
        had_d=had_d,
        had_a=had_a,
        hhad_goal_line=hhad_goal_line,
      )
      db.add(match)
      db.flush()
      stats['matches_new'] += 1
    else:
      if not match.home_team:
        match.home_team = home_team
      if not match.away_team:
        match.away_team = away_team
      if match.league_id != league.id:
        match.league_id = league.id
      if sporttery_mid and not match.sporttery_match_id:
        match.sporttery_match_id = sporttery_mid
      if is_finished:
        match.status = 'finished'
      match.had_h = had_h
      match.had_d = had_d
      match.had_a = had_a
      match.hhad_goal_line = hhad_goal_line
    stats['matches'] += 1

    # -- result from sectionsNo999 --
    score_str = (row.get('sectionsNo999') or '').strip()
    home_score, away_score = _parse_score(score_str)

    if is_finished and home_score is not None and away_score is not None:
      outcome = _classify_result(home_score, away_score)
      h_outcome = _classify_handicap(home_score, away_score, hhad_goal_line)
      existing_result = (
        db.query(SportteryMatchResult)
        .filter(SportteryMatchResult.match_id == match.id)
        .one_or_none()
      )
      if existing_result is None:
        db.add(SportteryMatchResult(
          match_id=match.id,
          home_score=home_score,
          away_score=away_score,
          result=outcome,
          handicap_result=h_outcome,
        ))
      else:
        existing_result.home_score = home_score
        existing_result.away_score = away_score
        existing_result.result = outcome
        existing_result.handicap_result = h_outcome
      stats['results'] += 1

    # -- titan007 odds via jc_code mapping --
    titan_mid = jc_to_titan.get(match_num_str)
    if titan_mid is not None:
      o = odds_by_tid.get(titan_mid)
      if o is not None:
        odds_row = (
          db.query(SportteryMatchOdds)
          .filter(
            SportteryMatchOdds.match_id == match.id,
            SportteryMatchOdds.source == 'titan007',
          )
          .one_or_none()
        )
        fields = {
          'win_odds': o.win_odds,
          'draw_odds': o.draw_odds,
          'lose_odds': o.lose_odds,
          'handicap_value': o.handicap_value,
          'asian_handicap': str(o.handicap_value) if o.handicap_value is not None else None,
          'win_handicap_odds': o.win_handicap_odds,
          'draw_handicap_odds': o.draw_handicap_odds,
          'lose_handicap_odds': o.lose_handicap_odds,
          'total_goals': None,
          'scraped_at': now,
        }
        if odds_row is None:
          db.add(SportteryMatchOdds(match_id=match.id, source='titan007', **fields))
        else:
          for k, v in fields.items():
            setattr(odds_row, k, v)
        stats['odds'] += 1

    if sporttery_mid:
      hhad_queue.append((match, sporttery_mid))
    if titan_mid is not None:
      stats_queue.append((match, titan_mid))

  # -- HHAD odds (Sporttery) + historical team stats (Titan007 analysis page) --
  _client = client or httpx.Client(timeout=15)
  try:
    for match_obj, s_mid in hhad_queue:
      if match_obj.hhad_h is None:
        hhad = _fetch_hhad_odds(_client, s_mid)
        if hhad:
          match_obj.hhad_h = hhad['hhad_h']
          match_obj.hhad_d = hhad['hhad_d']
          match_obj.hhad_a = hhad['hhad_a']
          stats['hhad'] += 1
          if stats_delay > 0:
            time.sleep(stats_delay)

    if fetch_team_stats:
      for match_obj, titan_mid in stats_queue:
        if _upsert_team_stats(
          db,
          match_obj,
          titan_mid,
          _client,
          delay=stats_delay,
        ):
          stats['team_stats'] += 1
  finally:
    if client is None:
      _client.close()

  return stats


# ---------------------------------------------------------------------------
# Run orchestration
# ---------------------------------------------------------------------------

def _log_run(
  db: Session,
  target: date,
  status: str,
  records: int,
  error: str | None,
  started_at: datetime,
  finished_at: datetime,
) -> None:
  db.add(ScrapeLog(
    job_name=SCRAPER_NAME,
    source='sporttery',
    status=status,
    records_count=records,
    error_message=f'date={target.isoformat()} {error}' if error else None,
    started_at=started_at,
    finished_at=finished_at,
  ))
  db.commit()


def run(
  start: date,
  end: date,
  *,
  force: bool,
  delay: float,
  fetch_team_stats: bool = True,
  stats_delay: float = 0.5,
) -> int:
  total_matches = 0
  total_results = 0
  total_odds = 0
  total_team_stats = 0
  failures: list[tuple[date, str]] = []

  with build_client(timeout=15.0) as client, SessionLocal() as db:
    for target in daterange(start, end):
      if not force and already_synced(db, target):
        logger.info('skip %s (already synced)', target)
        continue

      started = now_beijing()
      try:
        sporttery_rows, titan_matches, titan_odds = fetch_day(client, target)
        stats = upsert_day(
          db, target, sporttery_rows, titan_matches, titan_odds,
          client=client,
          fetch_team_stats=fetch_team_stats,
          stats_delay=stats_delay,
        )
        db.commit()
        finished = now_beijing()
        logger.info(
          'date=%s matches=%s (new=%s) results=%s odds=%s hhad=%s team_stats=%s',
          target,
          stats['matches'],
          stats['matches_new'],
          stats['results'],
          stats['odds'],
          stats['hhad'],
          stats['team_stats'],
        )
        _log_run(
          db, target, 'success', stats['matches'],
          None, started, finished,
        )
        total_matches += stats['matches']
        total_results += stats['results']
        total_odds += stats['odds']
        total_team_stats += stats['team_stats']
      except Exception as err:
        db.rollback()
        finished = now_beijing()
        msg = str(err)[:200]
        logger.warning('date=%s FAILED %s', target, msg)
        _log_run(db, target, 'failed', 0, msg, started, finished)
        failures.append((target, msg))

      if delay > 0:
        time.sleep(delay)

  print()
  print('=' * 60)
  print(f'Backfill complete: {start} -> {end}')
  print(f'  matches:    {total_matches}')
  print(f'  results:    {total_results}')
  print(f'  odds:       {total_odds}')
  print(f'  team_stats: {total_team_stats}')
  print(f'  failures:   {len(failures)}')
  for d, msg in failures:
    print(f'    - {d}: {msg}')
  return 0 if not failures else 2


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> date:
  return datetime.strptime(s, '%Y-%m-%d').date()


def main(argv: list[str] | None = None) -> int:
  logging.basicConfig(
    level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s'
  )
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
    '--from', dest='from_', required=True, type=_parse_date,
    help='start date (inclusive, YYYY-MM-DD)',
  )
  parser.add_argument(
    '--to', dest='to', required=True, type=_parse_date,
    help='end date (inclusive, YYYY-MM-DD)',
  )
  parser.add_argument(
    '--force', action='store_true',
    help='re-run dates that were already successfully synced',
  )
  parser.add_argument(
    '--delay', type=float, default=0.8,
    help='sleep seconds between days (default 0.8)',
  )
  parser.add_argument(
    '--no-stats', dest='no_stats', action='store_true',
    help='skip team_stats fetching (faster, odds+results only)',
  )
  parser.add_argument(
    '--stats-delay', type=float, default=0.5,
    help='sleep seconds between team-stats API calls (default 0.5)',
  )
  args = parser.parse_args(argv)

  if args.to < args.from_:
    parser.error('--to must be >= --from')
  return run(
    args.from_, args.to,
    force=args.force,
    delay=args.delay,
    fetch_team_stats=not args.no_stats,
    stats_delay=args.stats_delay,
  )


if __name__ == '__main__':
  sys.exit(main())

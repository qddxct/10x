"""Backfill Titan007 structured recent score fields for existing matches."""

from __future__ import annotations

import argparse
import logging
from datetime import date

import httpx
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.match import SportteryMatch
from app.models.team_stats import SportteryMatchTeamStats
from app.scrapers.http import build_client
from app.scripts.backfill import _upsert_team_stats, daterange, fetch_titan_day

logger = logging.getLogger(__name__)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _match_id_bounds(business_date: date) -> tuple[int, int]:
    prefix = int(f"{business_date:%Y%m%d}") * 10000
    return prefix, prefix + 9999


def _load_existing_matches(
    db: Session,
    business_date: date,
    *,
    missing_only: bool = False,
) -> list[SportteryMatch]:
    lower, upper = _match_id_bounds(business_date)
    query = (
        db.query(SportteryMatch)
        .filter(SportteryMatch.id >= lower, SportteryMatch.id <= upper)
    )
    if missing_only:
        query = query.outerjoin(
            SportteryMatchTeamStats,
            SportteryMatchTeamStats.match_id == SportteryMatch.id,
        ).filter(SportteryMatchTeamStats.home_recent_matches_count.is_(None))
    return query.order_by(SportteryMatch.id.asc()).all()


def backfill_range(
    db: Session,
    client: httpx.Client,
    *,
    start: date,
    end: date,
    delay: float,
    dry_run: bool = False,
    missing_only: bool = False,
) -> dict[str, int]:
    totals = {
        "days": 0,
        "candidates": 0,
        "mapped": 0,
        "updated": 0,
        "missing_mapping": 0,
        "titan_day_failed": 0,
        "team_stats_failed": 0,
    }

    for target in daterange(start, end):
        totals["days"] += 1
        matches = _load_existing_matches(db, target, missing_only=missing_only)
        totals["candidates"] += len(matches)
        if not matches:
            continue

        try:
            _leagues, titan_matches, _odds = fetch_titan_day(client, target)
        except Exception as err:  # pragma: no cover - network path
            logger.warning("date=%s titan day fetch failed: %s", target, err)
            totals["titan_day_failed"] += 1
            continue

        jc_to_titan = {
            item.jc_code: item.match_id
            for item in titan_matches
            if item.jc_code and item.match_id
        }

        day_updated = 0
        for match in matches:
            jc_code = (match.round or "").strip()
            titan_match_id = jc_to_titan.get(jc_code)
            if titan_match_id is None:
                totals["missing_mapping"] += 1
                continue
            totals["mapped"] += 1
            if dry_run:
                continue
            if _upsert_team_stats(db, match, titan_match_id, client, delay=delay):
                totals["updated"] += 1
                day_updated += 1
            else:
                totals["team_stats_failed"] += 1

        if not dry_run:
            db.commit()
        logger.info(
            "date=%s candidates=%s mapped=%s updated=%s",
            target,
            len(matches),
            sum(1 for match in matches if (match.round or "").strip() in jc_to_titan),
            day_updated,
        )

    return totals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, type=_parse_date)
    parser.add_argument("--end", required=True, type=_parse_date)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--missing-only", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    with SessionLocal() as db, build_client(timeout=20) as client:
        totals = backfill_range(
            db,
            client,
            start=args.start,
            end=args.end,
            delay=args.delay,
            dry_run=args.dry_run,
            missing_only=args.missing_only,
        )

    print(
        "Backfill Titan recent scores complete: "
        f"{args.start.isoformat()} -> {args.end.isoformat()}"
    )
    for key, value in totals.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

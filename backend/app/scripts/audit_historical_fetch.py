"""Audit historical fetch quality using sidecar tables.

This script fetches historical matches through the current source-boundary rules,
writes snapshots into ``data_audit_*`` tables, and compares them with production
sporttery tables. Production match/odds/result/team_stats tables are read-only.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.tz import now_beijing
from app.models.match import SportteryMatch
from app.models.match_id import build_logical_id, parse_jc_code
from app.models.odds import SportteryMatchOdds
from app.models.result import SportteryMatchResult
from app.models.team_stats import SportteryMatchTeamStats
from app.scrapers.http import build_client
from app.scrapers.titan007.analysis import fetch_analysis, parse_analysis
from app.scripts.backfill import (
    _classify_handicap,
    _classify_result,
    _dec,
    _parse_score,
    daterange,
    fetch_day,
)

logger = logging.getLogger(__name__)
DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}")

MATCH_FIELDS = [
    "jc_code",
    "league_name",
    "home_team",
    "away_team",
    "match_date",
    "had_h",
    "had_d",
    "had_a",
    "hhad_goal_line",
]
RESULT_FIELDS = ["home_score", "away_score", "result", "handicap_result"]
ODDS_FIELDS = [
    "win_odds",
    "draw_odds",
    "lose_odds",
    "handicap_value",
    "win_handicap_odds",
    "draw_handicap_odds",
    "lose_handicap_odds",
]
TEAM_STATS_FIELDS = [
    "home_rank",
    "away_rank",
    "home_season_wins",
    "home_season_draws",
    "home_season_losses",
    "away_season_wins",
    "away_season_draws",
    "away_season_losses",
    "home_recent_form",
    "away_recent_form",
    "h2h_home_wins",
    "h2h_draws",
    "h2h_away_wins",
    "home_recent_matches_count",
    "home_recent_goals_for",
    "home_recent_goals_against",
    "away_recent_matches_count",
    "away_recent_goals_for",
    "away_recent_goals_against",
    "h2h_matches_count",
    "h2h_draw_score_count",
    "h2h_one_goal_margin_count",
]


CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS data_audit_runs (
      id BIGINT PRIMARY KEY AUTO_INCREMENT,
      label VARCHAR(128) NOT NULL,
      start_date DATE NOT NULL,
      end_date DATE NOT NULL,
      status VARCHAR(32) NOT NULL,
      totals_json JSON NULL,
      report_path VARCHAR(512) NULL,
      error_message TEXT NULL,
      created_at DATETIME NOT NULL,
      finished_at DATETIME NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS data_audit_match_snapshots (
      id BIGINT PRIMARY KEY AUTO_INCREMENT,
      run_id BIGINT NOT NULL,
      match_id BIGINT NOT NULL,
      business_date DATE NOT NULL,
      jc_code VARCHAR(32) NULL,
      titan_match_id VARCHAR(32) NULL,
      league_name VARCHAR(128) NULL,
      home_team VARCHAR(128) NULL,
      away_team VARCHAR(128) NULL,
      match_date DATETIME NULL,
      match_json JSON NOT NULL,
      result_json JSON NULL,
      odds_json JSON NULL,
      team_stats_json JSON NULL,
      created_at DATETIME NOT NULL,
      UNIQUE KEY uq_data_audit_snapshot_run_match (run_id, match_id),
      KEY ix_data_audit_snapshot_run (run_id),
      KEY ix_data_audit_snapshot_match (match_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS data_audit_diffs (
      id BIGINT PRIMARY KEY AUTO_INCREMENT,
      run_id BIGINT NOT NULL,
      match_id BIGINT NOT NULL,
      section VARCHAR(32) NOT NULL,
      field_name VARCHAR(64) NOT NULL,
      existing_value TEXT NULL,
      audit_value TEXT NULL,
      severity VARCHAR(32) NOT NULL,
      created_at DATETIME NOT NULL,
      KEY ix_data_audit_diffs_run (run_id),
      KEY ix_data_audit_diffs_match (match_id),
      KEY ix_data_audit_diffs_field (section, field_name)
    )
    """,
]


def normalize_compare_value(value: Any) -> str | None:
    """Normalize values for stable audit comparison."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return _normalize_decimal(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _normalize_decimal(Decimal(str(value)))
    text_value = str(value).strip()
    if text_value == "":
        return None
    if DATE_ONLY_RE.match(text_value):
        return f"{text_value} 00:00:00"
    if DATETIME_RE.match(text_value):
        return text_value.replace("T", " ")[:19]
    try:
        return _normalize_decimal(Decimal(text_value))
    except InvalidOperation:
        return text_value


def _normalize_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f")


def compare_fields(
    *,
    match_id: int,
    section: str,
    existing: dict[str, Any],
    audit: dict[str, Any],
    fields: list[str],
) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    for field in fields:
        existing_value = normalize_compare_value(existing.get(field))
        audit_value = normalize_compare_value(audit.get(field))
        if existing_value == audit_value:
            continue
        if existing_value is None and audit_value is not None:
            severity = "missing_existing"
        elif existing_value is not None and audit_value is None:
            severity = "missing_audit"
        else:
            severity = "mismatch"
        diffs.append({
            "match_id": match_id,
            "section": section,
            "field_name": field,
            "existing_value": existing_value,
            "audit_value": audit_value,
            "severity": severity,
        })
    return diffs


def ensure_audit_tables(db: Session) -> None:
    for sql in CREATE_TABLES_SQL:
        db.execute(text(sql))
    db.commit()


def create_run(db: Session, *, label: str, start: date, end: date) -> int:
    result = db.execute(
        text(
            "INSERT INTO data_audit_runs "
            "(label, start_date, end_date, status, created_at) "
            "VALUES (:label, :start_date, :end_date, 'running', :created_at)"
        ),
        {
            "label": label,
            "start_date": start,
            "end_date": end,
            "created_at": now_beijing(),
        },
    )
    db.commit()
    return int(result.lastrowid)


def finish_run(
    db: Session,
    *,
    run_id: int,
    status: str,
    totals: dict[str, Any],
    report_path: str | None,
    error_message: str | None = None,
) -> None:
    db.execute(
        text(
            "UPDATE data_audit_runs SET status=:status, totals_json=:totals_json, "
            "report_path=:report_path, error_message=:error_message, finished_at=:finished_at "
            "WHERE id=:run_id"
        ),
        {
            "run_id": run_id,
            "status": status,
            "totals_json": json.dumps(totals, ensure_ascii=False, default=str),
            "report_path": report_path,
            "error_message": error_message,
            "finished_at": now_beijing(),
        },
    )
    db.commit()


def _json(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _team_stats_to_dict(stats: Any) -> dict[str, Any]:
    return {field: getattr(stats, field) for field in TEAM_STATS_FIELDS}


def build_snapshots_for_day(
    client: httpx.Client,
    business_date: date,
    *,
    analysis_delay: float,
) -> list[dict[str, Any]]:
    sporttery_rows, titan_matches, titan_odds = fetch_day(client, business_date)
    jc_to_titan = {tm.jc_code: tm.match_id for tm in titan_matches if tm.jc_code}
    odds_by_tid = {o.match_id: o for o in titan_odds}
    snapshots: list[dict[str, Any]] = []

    for row in sporttery_rows:
        jc_code = (row.get("matchNumStr") or "").strip()
        parsed = parse_jc_code(jc_code)
        if parsed is None:
            continue
        weekday, seq = parsed
        try:
            match_id = build_logical_id(business_date, weekday, seq)
        except ValueError:
            continue

        home_score, away_score = _parse_score((row.get("sectionsNo999") or "").strip())
        hhad_goal_line = _dec(row.get("goalLine"))
        result_json = None
        if home_score is not None and away_score is not None:
            result_json = {
                "home_score": home_score,
                "away_score": away_score,
                "result": _classify_result(home_score, away_score),
                "handicap_result": _classify_handicap(home_score, away_score, hhad_goal_line),
            }

        titan_match_id = jc_to_titan.get(jc_code)
        odds_json = None
        if titan_match_id:
            odds = odds_by_tid.get(titan_match_id)
            if odds is not None:
                odds_json = {
                    "win_odds": odds.win_odds,
                    "draw_odds": odds.draw_odds,
                    "lose_odds": odds.lose_odds,
                    "handicap_value": odds.handicap_value,
                    "win_handicap_odds": odds.win_handicap_odds,
                    "draw_handicap_odds": odds.draw_handicap_odds,
                    "lose_handicap_odds": odds.lose_handicap_odds,
                }

        home_team = (row.get("homeTeam") or "").strip()
        away_team = (row.get("awayTeam") or "").strip()
        team_stats_json = None
        if titan_match_id:
            try:
                html = fetch_analysis(client, titan_match_id, retry_delay=0.2)
                parsed_stats = parse_analysis(html, home_team, away_team)
                if parsed_stats is not None:
                    team_stats_json = _team_stats_to_dict(parsed_stats)
            except Exception as exc:  # pragma: no cover - network dependent
                logger.info(
                    "analysis audit failed date=%s jc=%s titan=%s err=%s",
                    business_date,
                    jc_code,
                    titan_match_id,
                    exc,
                )
            if analysis_delay > 0:
                time.sleep(analysis_delay)

        match_date_value = row.get("matchDate") or business_date.isoformat()
        match_json = {
            "jc_code": jc_code,
            "league_name": (row.get("leagueNameAbbr") or "unknown").strip() or "unknown",
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date_value,
            "had_h": _dec(row.get("h")),
            "had_d": _dec(row.get("d")),
            "had_a": _dec(row.get("a")),
            "hhad_goal_line": hhad_goal_line,
        }
        snapshots.append({
            "match_id": match_id,
            "business_date": business_date,
            "jc_code": jc_code,
            "titan_match_id": titan_match_id,
            "league_name": match_json["league_name"],
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date_value,
            "match_json": match_json,
            "result_json": result_json,
            "odds_json": odds_json,
            "team_stats_json": team_stats_json,
        })

    return snapshots


def insert_snapshot(db: Session, *, run_id: int, snapshot: dict[str, Any]) -> None:
    db.execute(
        text(
            "INSERT INTO data_audit_match_snapshots "
            "(run_id, match_id, business_date, jc_code, titan_match_id, league_name, "
            "home_team, away_team, match_date, match_json, result_json, odds_json, "
            "team_stats_json, created_at) VALUES "
            "(:run_id, :match_id, :business_date, :jc_code, :titan_match_id, :league_name, "
            ":home_team, :away_team, :match_date, :match_json, :result_json, :odds_json, "
            ":team_stats_json, :created_at) "
            "ON DUPLICATE KEY UPDATE titan_match_id=VALUES(titan_match_id), "
            "match_json=VALUES(match_json), result_json=VALUES(result_json), "
            "odds_json=VALUES(odds_json), team_stats_json=VALUES(team_stats_json)"
        ),
        {
            "run_id": run_id,
            "match_id": snapshot["match_id"],
            "business_date": snapshot["business_date"],
            "jc_code": snapshot["jc_code"],
            "titan_match_id": snapshot["titan_match_id"],
            "league_name": snapshot["league_name"],
            "home_team": snapshot["home_team"],
            "away_team": snapshot["away_team"],
            "match_date": _parse_match_datetime(snapshot["match_date"]),
            "match_json": _json(snapshot["match_json"]),
            "result_json": _json(snapshot["result_json"]),
            "odds_json": _json(snapshot["odds_json"]),
            "team_stats_json": _json(snapshot["team_stats_json"]),
            "created_at": now_beijing(),
        },
    )


def _parse_match_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    text_value = str(value)
    try:
        if "T" in text_value:
            return datetime.fromisoformat(text_value)
        if len(text_value) == 10:
            return datetime.strptime(text_value, "%Y-%m-%d")
        return datetime.strptime(text_value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _model_dict(obj: Any, fields: list[str]) -> dict[str, Any]:
    if obj is None:
        return {field: None for field in fields}
    return {field: getattr(obj, field, None) for field in fields}


def compare_snapshot(db: Session, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    match_id = snapshot["match_id"]
    match = db.get(SportteryMatch, match_id)
    existing_match = {field: None for field in MATCH_FIELDS}
    if match is not None:
        existing_match = {
            "jc_code": match.round,
            "league_name": match.league.name if match.league else None,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "match_date": match.match_date,
            "had_h": match.had_h,
            "had_d": match.had_d,
            "had_a": match.had_a,
            "hhad_goal_line": match.hhad_goal_line,
        }

    result = (
        db.query(SportteryMatchResult)
        .filter(SportteryMatchResult.match_id == match_id)
        .one_or_none()
    )
    odds = (
        db.query(SportteryMatchOdds)
        .filter(
            SportteryMatchOdds.match_id == match_id,
            SportteryMatchOdds.source == "titan007",
        )
        .one_or_none()
    )
    team_stats = (
        db.query(SportteryMatchTeamStats)
        .filter(SportteryMatchTeamStats.match_id == match_id)
        .one_or_none()
    )

    diffs: list[dict[str, Any]] = []
    diffs.extend(compare_fields(
        match_id=match_id,
        section="match",
        existing=existing_match,
        audit=snapshot["match_json"] or {},
        fields=MATCH_FIELDS,
    ))
    diffs.extend(compare_fields(
        match_id=match_id,
        section="result",
        existing=_model_dict(result, RESULT_FIELDS),
        audit=snapshot["result_json"] or {},
        fields=RESULT_FIELDS,
    ))
    diffs.extend(compare_fields(
        match_id=match_id,
        section="odds",
        existing=_model_dict(odds, ODDS_FIELDS),
        audit=snapshot["odds_json"] or {},
        fields=ODDS_FIELDS,
    ))
    diffs.extend(compare_fields(
        match_id=match_id,
        section="team_stats",
        existing=_model_dict(team_stats, TEAM_STATS_FIELDS),
        audit=snapshot["team_stats_json"] or {},
        fields=TEAM_STATS_FIELDS,
    ))
    return diffs


def insert_diffs(db: Session, *, run_id: int, diffs: list[dict[str, Any]]) -> None:
    if not diffs:
        return
    db.execute(
        text("DELETE FROM data_audit_diffs WHERE run_id=:run_id AND match_id=:match_id"),
        {"run_id": run_id, "match_id": diffs[0]["match_id"]},
    )
    for diff in diffs:
        db.execute(
            text(
                "INSERT INTO data_audit_diffs "
                "(run_id, match_id, section, field_name, existing_value, "
                "audit_value, severity, created_at) "
                "VALUES (:run_id, :match_id, :section, :field_name, "
                ":existing_value, :audit_value, :severity, :created_at)"
            ),
            {**diff, "run_id": run_id, "created_at": now_beijing()},
        )


def run_audit(
    *,
    start: date,
    end: date,
    label: str,
    delay: float,
    analysis_delay: float,
    report: Path,
) -> int:
    totals: dict[str, Any] = {
        "days": 0,
        "snapshots": 0,
        "snapshots_with_titan_mapping": 0,
        "snapshots_with_odds": 0,
        "snapshots_with_team_stats": 0,
        "diffs": 0,
        "failures": [],
    }
    with SessionLocal() as db:
        ensure_audit_tables(db)
        run_id = create_run(db, label=label, start=start, end=end)
        try:
            with build_client(timeout=20) as client:
                for target in daterange(start, end):
                    totals["days"] += 1
                    try:
                        snapshots = build_snapshots_for_day(
                            client,
                            target,
                            analysis_delay=analysis_delay,
                        )
                    except Exception as exc:  # pragma: no cover - network dependent
                        msg = f"{target}: {exc}"
                        logger.warning("audit day failed %s", msg)
                        totals["failures"].append(msg)
                        continue

                    for snapshot in snapshots:
                        insert_snapshot(db, run_id=run_id, snapshot=snapshot)
                        diffs = compare_snapshot(db, snapshot)
                        insert_diffs(db, run_id=run_id, diffs=diffs)
                        totals["snapshots"] += 1
                        totals["snapshots_with_titan_mapping"] += int(
                            bool(snapshot["titan_match_id"])
                        )
                        totals["snapshots_with_odds"] += int(bool(snapshot["odds_json"]))
                        totals["snapshots_with_team_stats"] += int(
                            bool(snapshot["team_stats_json"])
                        )
                        totals["diffs"] += len(diffs)
                    db.commit()
                    logger.info("audit date=%s snapshots=%s", target, len(snapshots))
                    if delay > 0:
                        time.sleep(delay)

            write_report(db, run_id=run_id, start=start, end=end, totals=totals, path=report)
            finish_run(
                db,
                run_id=run_id,
                status="success" if not totals["failures"] else "partial",
                totals=totals,
                report_path=str(report),
            )
        except Exception as exc:
            db.rollback()
            finish_run(
                db,
                run_id=run_id,
                status="failed",
                totals=totals,
                report_path=str(report),
                error_message=str(exc)[:1000],
            )
            raise
    print(f"Audit run #{run_id} complete, report: {report}")
    return 0 if not totals["failures"] else 2


def write_report(
    db: Session,
    *,
    run_id: int,
    start: date,
    end: date,
    totals: dict[str, Any],
    path: Path,
) -> None:
    rows = db.execute(
        text(
            "SELECT section, field_name, severity, COUNT(*) AS cnt "
            "FROM data_audit_diffs WHERE run_id=:run_id "
            "GROUP BY section, field_name, severity ORDER BY cnt DESC LIMIT 30"
        ),
        {"run_id": run_id},
    ).mappings().all()
    severity_rows = db.execute(
        text(
            "SELECT severity, COUNT(*) AS cnt FROM data_audit_diffs "
            "WHERE run_id=:run_id GROUP BY severity ORDER BY cnt DESC"
        ),
        {"run_id": run_id},
    ).mappings().all()

    severity_counter = Counter({row["severity"]: row["cnt"] for row in severity_rows})
    section_counter: dict[str, int] = defaultdict(int)
    for row in rows:
        section_counter[row["section"]] += row["cnt"]

    lines = [
        "# 历史抓取旁路审计报告",
        "",
        f"- 审计 run: #{run_id}",
        f"- 日期范围: {start.isoformat()} -> {end.isoformat()}",
        f"- 新抓快照场次: {totals['snapshots']}",
        f"- 有 Titan007 映射: {totals['snapshots_with_titan_mapping']}",
        f"- 有 Titan007 欧赔: {totals['snapshots_with_odds']}",
        f"- 有 Titan007 analysis 状态: {totals['snapshots_with_team_stats']}",
        f"- 字段级差异: {totals['diffs']}",
        "",
        "## 差异严重程度",
        "",
        "| 类型 | 数量 |",
        "|---|---:|",
    ]
    for key in ["missing_existing", "missing_audit", "mismatch"]:
        lines.append(f"| {key} | {severity_counter.get(key, 0)} |")

    if totals["diffs"] == 0 and totals["snapshots"] > 0:
        conclusion = (
            "本次旁路新抓数据与正式表在纳入对比的字段上完全一致, "
            "暂未发现数据质量差异。"
        )
    elif totals["snapshots"] == 0:
        conclusion = "本次日期范围没有抓到可审计比赛, 需要更换日期范围。"
    else:
        conclusion = "本次发现字段级差异, 需要按下方 Top 字段抽样核验网页。"

    lines.extend(["", "## 结论", "", conclusion])

    lines.extend([
        "",
        "## 差异字段 Top 30",
        "",
        "| 分类 | 字段 | 类型 | 数量 |",
        "|---|---|---|---:|",
    ])
    for row in rows:
        lines.append(
            f"| {row['section']} | {row['field_name']} | "
            f"{row['severity']} | {row['cnt']} |"
        )

    if totals["failures"]:
        lines.extend(["", "## 抓取失败日期", ""])
        lines.extend(f"- {item}" for item in totals["failures"])

    lines.extend([
        "",
        "## 初步解读",
        "",
        "- `missing_existing` 多, 说明正式表可能缺数据, 新链路能补齐。",
        "- `missing_audit` 多, 说明新抓链路覆盖不足, "
        "需要优先查 Titan007 映射或 analysis 页面。",
        "- `mismatch` 多, 说明两边都有值但不同, 需要抽样打开网页核验。",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def default_month_range(db: Session) -> tuple[date, date]:
    row = db.execute(
        text("SELECT MIN(DATE(match_date)) AS min_d FROM sporttery_matches")
    ).mappings().one()
    min_date = row["min_d"]
    if min_date is None:
        end = date.today()
        return end - timedelta(days=30), end
    start = min_date
    return start, start + timedelta(days=30)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=_parse_date)
    parser.add_argument("--end", type=_parse_date)
    parser.add_argument("--label", default="historical-fetch-audit")
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--analysis-delay", type=float, default=0.5)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("docs/analysis/2026-04-26-historical-fetch-audit.md"),
    )
    args = parser.parse_args(argv)

    if args.start is None or args.end is None:
        with SessionLocal() as db:
            default_start, default_end = default_month_range(db)
        start = args.start or default_start
        end = args.end or default_end
    else:
        start = args.start
        end = args.end
    if end < start:
        parser.error("--end must be >= --start")
    return run_audit(
        start=start,
        end=end,
        label=args.label,
        delay=args.delay,
        analysis_delay=args.analysis_delay,
        report=args.report,
    )


if __name__ == "__main__":
    sys.exit(main())

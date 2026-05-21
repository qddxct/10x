# V3.1/V4 Incremental Signal Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only analysis workflow that validates additional draw and handicap-draw signals before any model logic is changed.

**Architecture:** Add a focused analysis module and CLI script that load complete historical matches, compute currently available features, report data gaps, split Draw/Handicap Draw channels, and write a Markdown validation report. The existing `default`, `empirical-v2-d104-h104-clean`, and `empirical-v3-candidate` scoring logic must not be modified by this work.

**Tech Stack:** Python 3.11, SQLAlchemy ORM, Pytest, MySQL in Docker, Markdown reports under `docs/analysis`.

---

## Source Design

This plan implements: `docs/superpowers/specs/2026-04-26-v31-v4-incremental-signal-validation-design.md`.

Key constraints:

- Do not change model recommendation logic.
- Do not activate or deactivate model configs.
- Do not mutate match, odds, result, team-stat, score, or backtest data.
- Use only historical data available before the match.
- Split ordinary draw and handicap draw into separate analysis channels.

## Current Data Reality

Existing structured fields that can be analyzed immediately:

- Match metadata: `match_date`, `league`, `home_team`, `away_team`, `competition_type`.
- Result: `home_score`, `away_score`, `result`, `handicap_result`.
- Sporttery settlement odds: `had_d`, `hhad_d`, `hhad_goal_line`.
- Titan007 odds snapshot: `win_odds`, `draw_odds`, `lose_odds`, `handicap_value`, `win_handicap_odds`, `lose_handicap_odds`.
- Team snapshot: ranks, season W/D/L, home/away W/D/L, recent W/D/L string, H2H W/D/L.

Known gaps to report, not fabricate:

- No structured recent match scores for each team.
- No structured team goals-for/goals-against totals.
- No structured one-goal win/loss distributions.
- No multi-point odds movement history; current stored odds are latest available snapshot from the historical source.
- No structured schedule-pressure or injury fields.

## File Structure

Create these files:

- `backend/app/scripts/incremental_signal_validation.py`: read-only CLI that loads rows, computes feature buckets, writes Markdown report.
- `backend/tests/test_incremental_signal_validation.py`: unit tests for pure helpers and rule predicates.
- `docs/analysis/2026-04-26-v31-v4-incremental-signal-validation.md`: generated report.

Do not modify these files unless a test exposes a defect in reusable logic:

- `backend/app/engine/scoring.py`
- `backend/app/engine/service.py`
- `backend/app/scripts/seed.py`

## Task 1: Pure Feature Helper Tests

**Files:**
- Create: `backend/tests/test_incremental_signal_validation.py`
- Create: `backend/app/scripts/incremental_signal_validation.py`

- [ ] **Step 1: Write failing helper tests**

Create `backend/tests/test_incremental_signal_validation.py`:

```python
from __future__ import annotations

from app.scripts.incremental_signal_validation import (
    bucket,
    calculate_stats,
    goal_margin,
    is_hdraw_a,
    roi,
    safe_rate,
)


def test_safe_rate_handles_missing_and_zero_denominator():
    assert safe_rate(None, 10) is None
    assert safe_rate(3, None) is None
    assert safe_rate(3, 0) is None
    assert safe_rate(3, 10) == 0.3


def test_goal_margin_returns_home_minus_away():
    assert goal_margin(2, 1) == 1
    assert goal_margin(1, 3) == -2


def test_roi_uses_fixed_100_unit_stake():
    assert roi([150.0, -100.0, -100.0]) == -50.0 / 300.0


def test_bucket_labels_edges():
    assert bucket(None, [0, 1, 2], ["0-1", "1-2", ">=2"]) == "NA"
    assert bucket(0.5, [0, 1, 2], ["0-1", "1-2", ">=2"]) == "0-1"
    assert bucket(1.5, [0, 1, 2], ["0-1", "1-2", ">=2"]) == "1-2"
    assert bucket(3, [0, 1, 2], ["0-1", "1-2", ">=2"]) == ">=2"


def test_calculate_stats_for_draw_channel():
    rows = [
        {"is_draw": True, "had_d": 3.2},
        {"is_draw": False, "had_d": 3.1},
        {"is_draw": True, "had_d": None},
    ]

    stats = calculate_stats(rows, target="draw")

    assert stats.bets == 2
    assert stats.hits == 1
    assert stats.hit_rate == 0.5
    assert round(stats.roi, 4) == 0.6000


def test_calculate_stats_for_handicap_draw_channel():
    rows = [
        {"is_hdraw": True, "hhad_d": 3.6},
        {"is_hdraw": False, "hhad_d": 3.4},
    ]

    stats = calculate_stats(rows, target="hdraw")

    assert stats.bets == 2
    assert stats.hits == 1
    assert round(stats.roi, 4) == 0.8000


def test_is_hdraw_a_matches_current_v3_rule():
    row = {
        "hcap": 1.25,
        "rank_gap": 8,
        "hhad_d": 3.6,
        "venue_draw_sum": 0.5,
        "season_draw_sum": 0.45,
    }

    assert is_hdraw_a(row) is True
    assert is_hdraw_a({**row, "rank_gap": 3}) is False
    assert is_hdraw_a({**row, "hhad_d": 3.4}) is False
    assert is_hdraw_a({**row, "hcap": 1.5}) is False
    assert is_hdraw_a({**row, "venue_draw_sum": 0.2}) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_incremental_signal_validation.py -q
```

Expected: FAIL because `app.scripts.incremental_signal_validation` does not exist.

- [ ] **Step 3: Add minimal helper implementation**

Create `backend/app/scripts/incremental_signal_validation.py`:

```python
"""Read-only incremental signal validation for draw and handicap-draw models."""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.engine.service import _pick_odds
from app.models import League, SportteryMatch, SportteryMatchResult, SportteryMatchTeamStats

Row = dict[str, Any]
Target = str


@dataclass(frozen=True)
class Stats:
    bets: int
    hits: int
    hit_rate: float
    pnl: float
    roi: float
    avg_odds: float


def safe_rate(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def goal_margin(home_score: int, away_score: int) -> int:
    return home_score - away_score


def roi(pnls: Iterable[float]) -> float:
    values = list(pnls)
    return sum(values) / (len(values) * 100) if values else 0.0


def bucket(value: float | None, edges: list[float], labels: list[str]) -> str:
    if value is None:
        return "NA"
    for idx, (low, high) in enumerate(pairwise(edges)):
        if low <= value < high:
            return labels[idx]
    return labels[-1]


def _odds_key(target: Target) -> str:
    return "had_d" if target == "draw" else "hhad_d"


def _hit_key(target: Target) -> str:
    return "is_draw" if target == "draw" else "is_hdraw"


def calculate_stats(rows: Iterable[Row], *, target: Target) -> Stats:
    odds_key = _odds_key(target)
    hit_key = _hit_key(target)
    usable = [row for row in rows if row.get(odds_key) is not None]
    bets = len(usable)
    hits = sum(1 for row in usable if row[hit_key])
    pnls = [
        (float(row[odds_key]) - 1) * 100 if row[hit_key] else -100
        for row in usable
    ]
    avg_odds = sum(float(row[odds_key]) for row in usable) / bets if bets else 0.0
    return Stats(
        bets=bets,
        hits=hits,
        hit_rate=hits / bets if bets else 0.0,
        pnl=sum(pnls),
        roi=roi(pnls),
        avg_odds=avg_odds,
    )


def is_hdraw_a(row: Row) -> bool:
    hcap = row.get("hcap")
    rank_gap = row.get("rank_gap")
    hhad_d = row.get("hhad_d")
    venue_sum = row.get("venue_draw_sum")
    season_sum = row.get("season_draw_sum")
    if hcap is None or abs(float(hcap)) >= 1.5:
        return False
    if venue_sum is not None and float(venue_sum) < 0.35:
        return False
    if season_sum is not None and float(season_sum) < 0.35:
        return False
    return (
        1.00 <= abs(float(hcap)) <= 1.25
        and rank_gap is not None
        and 6 <= float(rank_gap) <= 15
        and hhad_d is not None
        and float(hhad_d) >= 3.50
    )
```

- [ ] **Step 4: Run helper tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_incremental_signal_validation.py -q
```

Expected: PASS.

## Task 2: Historical Row Loader And Data Gap Report

**Files:**
- Modify: `backend/app/scripts/incremental_signal_validation.py`
- Modify: `backend/tests/test_incremental_signal_validation.py`

- [ ] **Step 1: Add tests for row enrichment and data gaps**

Append to `backend/tests/test_incremental_signal_validation.py`:

```python
from app.scripts.incremental_signal_validation import (
    data_gap_rows,
    enrich_row_features,
)


def test_enrich_row_features_computes_rates_and_margin():
    row = {
        "home_score": 2,
        "away_score": 1,
        "home_season_wins": 10,
        "home_season_draws": 5,
        "home_season_losses": 5,
        "away_season_wins": 6,
        "away_season_draws": 4,
        "away_season_losses": 10,
        "home_home_wins": 7,
        "home_home_draws": 2,
        "home_home_losses": 1,
        "away_away_wins": 2,
        "away_away_draws": 3,
        "away_away_losses": 5,
        "home_rank": 3,
        "away_rank": 12,
        "h2h_home_wins": 2,
        "h2h_draws": 1,
        "h2h_away_wins": 1,
        "home_recent_form": "WWDL",
        "away_recent_form": "LLDW",
    }

    out = enrich_row_features(row)

    assert out["goal_margin"] == 1
    assert out["rank_gap"] == 9
    assert out["season_draw_sum"] == 0.45
    assert out["venue_draw_sum"] == 0.5
    assert out["h2h_draw_rate"] == 0.25
    assert out["home_recent_win_rate"] == 0.5
    assert out["away_recent_loss_rate"] == 0.5


def test_data_gap_rows_reports_missing_structured_dimensions():
    rows = [
        {"home_recent_form": "WWDL", "h2h_draw_rate": 0.25},
        {"home_recent_form": None, "h2h_draw_rate": None},
    ]

    gaps = data_gap_rows(rows)

    names = {row[0] for row in gaps}
    assert "structured_recent_scores" in names
    assert "goals_for_against" in names
    assert "odds_movement_history" in names
    assert "recent_form_wdl" in names
    assert "h2h_wdl" in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_incremental_signal_validation.py -q
```

Expected: FAIL because `enrich_row_features` and `data_gap_rows` are missing.

- [ ] **Step 3: Implement enrichment and data gap functions**

Add to `backend/app/scripts/incremental_signal_validation.py`:

```python
def _sum_ints(*values: int | None) -> int:
    return sum(value or 0 for value in values)


def _form_rate(form: str | None, char: str) -> float | None:
    if not form:
        return None
    text = form.upper()
    return text.count(char) / len(text) if text else None


def enrich_row_features(row: Row) -> Row:
    item = dict(row)
    item["goal_margin"] = goal_margin(item["home_score"], item["away_score"])

    if item.get("home_rank") is not None and item.get("away_rank") is not None:
        item["rank_gap"] = abs(item["home_rank"] - item["away_rank"])
    else:
        item["rank_gap"] = None

    home_season_total = _sum_ints(
        item.get("home_season_wins"),
        item.get("home_season_draws"),
        item.get("home_season_losses"),
    )
    away_season_total = _sum_ints(
        item.get("away_season_wins"),
        item.get("away_season_draws"),
        item.get("away_season_losses"),
    )
    home_venue_total = _sum_ints(
        item.get("home_home_wins"),
        item.get("home_home_draws"),
        item.get("home_home_losses"),
    )
    away_venue_total = _sum_ints(
        item.get("away_away_wins"),
        item.get("away_away_draws"),
        item.get("away_away_losses"),
    )
    h2h_total = _sum_ints(
        item.get("h2h_home_wins"),
        item.get("h2h_draws"),
        item.get("h2h_away_wins"),
    )

    home_season_draw = safe_rate(item.get("home_season_draws"), home_season_total)
    away_season_draw = safe_rate(item.get("away_season_draws"), away_season_total)
    home_venue_draw = safe_rate(item.get("home_home_draws"), home_venue_total)
    away_venue_draw = safe_rate(item.get("away_away_draws"), away_venue_total)

    item["season_draw_sum"] = (
        home_season_draw + away_season_draw
        if home_season_draw is not None and away_season_draw is not None
        else None
    )
    item["venue_draw_sum"] = (
        home_venue_draw + away_venue_draw
        if home_venue_draw is not None and away_venue_draw is not None
        else None
    )
    item["h2h_draw_rate"] = safe_rate(item.get("h2h_draws"), h2h_total)
    item["home_recent_win_rate"] = _form_rate(item.get("home_recent_form"), "W")
    item["home_recent_draw_rate"] = _form_rate(item.get("home_recent_form"), "D")
    item["away_recent_loss_rate"] = _form_rate(item.get("away_recent_form"), "L")
    item["away_recent_draw_rate"] = _form_rate(item.get("away_recent_form"), "D")
    item["recent_draw_sum"] = (
        item["home_recent_draw_rate"] + item["away_recent_draw_rate"]
        if item["home_recent_draw_rate"] is not None
        and item["away_recent_draw_rate"] is not None
        else None
    )
    return item


def _coverage(rows: list[Row], key: str) -> str:
    total = len(rows)
    present = sum(1 for row in rows if row.get(key) is not None)
    pct = present / total if total else 0.0
    return f"{present}/{total} ({pct:.2%})"


def data_gap_rows(rows: list[Row]) -> list[list[str]]:
    return [
        ["recent_form_wdl", _coverage(rows, "home_recent_form"), "available"],
        ["h2h_wdl", _coverage(rows, "h2h_draw_rate"), "available"],
        ["structured_recent_scores", "0/0 (0.00%)", "missing"],
        ["goals_for_against", "0/0 (0.00%)", "missing"],
        ["one_goal_margin_distribution", "0/0 (0.00%)", "missing"],
        ["odds_movement_history", "0/0 (0.00%)", "missing"],
        ["schedule_pressure", "0/0 (0.00%)", "missing"],
        ["injury_absence", "0/0 (0.00%)", "missing"],
    ]
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_incremental_signal_validation.py -q
```

Expected: PASS.

- [ ] **Step 5: Implement DB row loader**

Add to `backend/app/scripts/incremental_signal_validation.py`:

```python
def _float(value: Any) -> float | None:
    return float(value) if value is not None else None


def load_rows(db: Session, *, start: date, end: date) -> list[Row]:
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    query = (
        db.query(SportteryMatch, SportteryMatchResult, League, SportteryMatchTeamStats)
        .join(SportteryMatchResult, SportteryMatchResult.match_id == SportteryMatch.id)
        .join(League, League.id == SportteryMatch.league_id)
        .join(SportteryMatchTeamStats, SportteryMatchTeamStats.match_id == SportteryMatch.id)
        .filter(SportteryMatch.match_date >= start_dt, SportteryMatch.match_date <= end_dt)
        .order_by(SportteryMatch.match_date.asc())
    )

    rows: list[Row] = []
    for match, result, league, stats in query:
        odds = _pick_odds(list(match.odds))
        if odds is None:
            continue
        raw = {
            "match_id": match.id,
            "match_date": match.match_date.date(),
            "month": match.match_date.strftime("%Y-%m"),
            "league": league.name,
            "competition_type": match.competition_type,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "home_score": result.home_score,
            "away_score": result.away_score,
            "is_draw": result.result == "draw",
            "is_hdraw": result.handicap_result == "draw",
            "had_d": _float(match.had_d),
            "hhad_d": _float(match.hhad_d),
            "hcap": _float(odds.handicap_value),
            "win_odds": _float(odds.win_odds),
            "draw_odds": _float(odds.draw_odds),
            "lose_odds": _float(odds.lose_odds),
            "handicap_draw_odds": _float(odds.draw_handicap_odds),
            "home_rank": stats.home_rank,
            "away_rank": stats.away_rank,
            "home_season_wins": stats.home_season_wins,
            "home_season_draws": stats.home_season_draws,
            "home_season_losses": stats.home_season_losses,
            "away_season_wins": stats.away_season_wins,
            "away_season_draws": stats.away_season_draws,
            "away_season_losses": stats.away_season_losses,
            "home_home_wins": stats.home_home_wins,
            "home_home_draws": stats.home_home_draws,
            "home_home_losses": stats.home_home_losses,
            "away_away_wins": stats.away_away_wins,
            "away_away_draws": stats.away_away_draws,
            "away_away_losses": stats.away_away_losses,
            "home_recent_form": stats.home_recent_form,
            "away_recent_form": stats.away_recent_form,
            "h2h_home_wins": stats.h2h_home_wins,
            "h2h_draws": stats.h2h_draws,
            "h2h_away_wins": stats.h2h_away_wins,
        }
        rows.append(enrich_row_features(raw))
    return rows
```

## Task 3: Channel And Bucket Analysis

**Files:**
- Modify: `backend/app/scripts/incremental_signal_validation.py`
- Modify: `backend/tests/test_incremental_signal_validation.py`

- [ ] **Step 1: Add tests for bucket summaries and window summaries**

Append:

```python
from datetime import date

from app.scripts.incremental_signal_validation import (
    bucket_summary,
    non_overlapping_windows,
    window_summary,
)


def test_bucket_summary_groups_rows_by_feature():
    rows = [
        {"league_group": "A", "is_hdraw": True, "hhad_d": 3.6},
        {"league_group": "A", "is_hdraw": False, "hhad_d": 3.6},
        {"league_group": "B", "is_hdraw": True, "hhad_d": 3.4},
    ]

    summary = bucket_summary(rows, key="league_group", target="hdraw", min_bets=1)

    assert summary[0][0] in {"A", "B"}
    assert {row[0] for row in summary} == {"A", "B"}


def test_non_overlapping_windows_covers_date_range():
    windows = non_overlapping_windows(date(2026, 1, 1), date(2026, 4, 10), days=90)

    assert windows == [
        (date(2026, 1, 1), date(2026, 3, 31)),
        (date(2026, 4, 1), date(2026, 4, 10)),
    ]


def test_window_summary_filters_rows_by_date():
    rows = [
        {"match_date": date(2026, 1, 1), "is_draw": True, "had_d": 3.2},
        {"match_date": date(2026, 4, 1), "is_draw": False, "had_d": 3.1},
    ]

    summary = window_summary(
        rows,
        target="draw",
        start=date(2026, 1, 1),
        end=date(2026, 3, 31),
    )

    assert summary.bets == 1
    assert summary.hits == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_incremental_signal_validation.py -q
```

Expected: FAIL because summary functions are missing.

- [ ] **Step 3: Implement summary functions**

Add:

```python
def _fmt_pct(value: float) -> str:
    return f"{value:.2%}"


def _fmt_float(value: float) -> str:
    return f"{value:.2f}"


def stats_row(label: str, stats: Stats) -> list[str | int]:
    return [
        label,
        stats.bets,
        stats.hits,
        _fmt_pct(stats.hit_rate),
        _fmt_pct(stats.roi),
        _fmt_float(stats.avg_odds),
    ]


def bucket_summary(rows: list[Row], *, key: str, target: Target, min_bets: int) -> list[list[Any]]:
    groups: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key, "NA"))].append(row)
    out = []
    for label, group_rows in groups.items():
        stats = calculate_stats(group_rows, target=target)
        if stats.bets >= min_bets:
            out.append(stats_row(label, stats))
    return sorted(out, key=lambda row: (row[4], row[3], row[1]), reverse=True)


def non_overlapping_windows(start: date, end: date, *, days: int) -> list[tuple[date, date]]:
    windows = []
    cursor = start
    while cursor <= end:
        window_end = min(cursor + timedelta(days=days - 1), end)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return windows


def window_summary(rows: list[Row], *, target: Target, start: date, end: date) -> Stats:
    selected = [row for row in rows if start <= row["match_date"] <= end]
    return calculate_stats(selected, target=target)
```

- [ ] **Step 4: Add feature bucket enrichment**

Add:

```python
def add_analysis_buckets(rows: list[Row]) -> list[Row]:
    enriched = []
    for row in rows:
        item = dict(row)
        item["abs_hcap_bucket"] = bucket(
            abs(item["hcap"]) if item.get("hcap") is not None else None,
            [0, 0.26, 0.76, 1.01, 1.26, 1.51, 99],
            ["0-0.25", "0.5-0.75", "1.0", "1.25", "1.5", ">1.5"],
        )
        item["rank_gap_bucket"] = bucket(
            item.get("rank_gap"),
            [0, 3, 6, 11, 16, 99],
            ["0-2", "3-5", "6-10", "11-15", ">=16"],
        )
        item["season_draw_sum_bucket"] = bucket(
            item.get("season_draw_sum"),
            [0, 0.35, 0.45, 0.55, 0.65, 2],
            ["<0.35", "0.35-0.45", "0.45-0.55", "0.55-0.65", ">=0.65"],
        )
        item["venue_draw_sum_bucket"] = bucket(
            item.get("venue_draw_sum"),
            [0, 0.35, 0.45, 0.55, 0.65, 2],
            ["<0.35", "0.35-0.45", "0.45-0.55", "0.55-0.65", ">=0.65"],
        )
        item["h2h_draw_rate_bucket"] = bucket(
            item.get("h2h_draw_rate"),
            [0, 0.2, 0.35, 0.5, 1.1],
            ["<0.20", "0.20-0.35", "0.35-0.50", ">=0.50"],
        )
        item["home_recent_win_bucket"] = bucket(
            item.get("home_recent_win_rate"),
            [0, 0.34, 0.51, 0.67, 1.1],
            ["<0.34", "0.34-0.50", "0.50-0.67", ">=0.67"],
        )
        item["away_recent_loss_bucket"] = bucket(
            item.get("away_recent_loss_rate"),
            [0, 0.34, 0.51, 0.67, 1.1],
            ["<0.34", "0.34-0.50", "0.50-0.67", ">=0.67"],
        )
        item["league_group"] = item.get("league") or "NA"
        enriched.append(item)
    return enriched
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_incremental_signal_validation.py -q
```

Expected: PASS.

## Task 4: Candidate Rule Analysis

**Files:**
- Modify: `backend/app/scripts/incremental_signal_validation.py`
- Modify: `backend/tests/test_incremental_signal_validation.py`

- [ ] **Step 1: Add tests for candidate predicates**

Append:

```python
from app.scripts.incremental_signal_validation import draw_candidate_rules, hdraw_candidate_rules


def test_hdraw_candidate_rules_include_hdraw_a_and_h2h_filters():
    names = [rule.name for rule in hdraw_candidate_rules()]

    assert "HDRAW_A current" in names
    assert "H2H draw rate >= 0.35" in names
    assert "Home recent win rate < 0.67" in names


def test_draw_candidate_rules_include_shallow_and_balanced_markets():
    names = [rule.name for rule in draw_candidate_rules()]

    assert "Shallow handicap <= 0.25" in names
    assert "Macau draw odds 3.00-3.20" in names
    assert "Rank gap <= 5" in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_incremental_signal_validation.py -q
```

Expected: FAIL because candidate rules are missing.

- [ ] **Step 3: Implement rule dataclass and predicates**

Add:

```python
@dataclass(frozen=True)
class CandidateRule:
    name: str
    channel: Target
    family: str
    fn: Any


def draw_candidate_rules() -> list[CandidateRule]:
    return [
        CandidateRule(
            "Shallow handicap <= 0.25",
            "draw",
            "hcap",
            lambda row: row.get("hcap") is not None and abs(row["hcap"]) <= 0.25,
        ),
        CandidateRule(
            "Macau draw odds 3.00-3.20",
            "draw",
            "draw_odds",
            lambda row: row.get("draw_odds") is not None and 3.00 <= row["draw_odds"] <= 3.20,
        ),
        CandidateRule(
            "Rank gap <= 5",
            "draw",
            "rank",
            lambda row: row.get("rank_gap") is not None and row["rank_gap"] <= 5,
        ),
        CandidateRule(
            "H2H draw rate >= 0.35",
            "draw",
            "h2h",
            lambda row: row.get("h2h_draw_rate") is not None and row["h2h_draw_rate"] >= 0.35,
        ),
        CandidateRule(
            "Recent draw sum >= 0.50",
            "draw",
            "recent",
            lambda row: row.get("recent_draw_sum") is not None and row["recent_draw_sum"] >= 0.50,
        ),
    ]


def hdraw_candidate_rules() -> list[CandidateRule]:
    return [
        CandidateRule("HDRAW_A current", "hdraw", "baseline", is_hdraw_a),
        CandidateRule(
            "H2H draw rate >= 0.35",
            "hdraw",
            "h2h",
            lambda row: row.get("h2h_draw_rate") is not None and row["h2h_draw_rate"] >= 0.35,
        ),
        CandidateRule(
            "Home recent win rate < 0.67",
            "hdraw",
            "recent_home",
            lambda row: row.get("home_recent_win_rate") is not None
            and row["home_recent_win_rate"] < 0.67,
        ),
        CandidateRule(
            "Away recent loss rate < 0.67",
            "hdraw",
            "recent_away",
            lambda row: row.get("away_recent_loss_rate") is not None
            and row["away_recent_loss_rate"] < 0.67,
        ),
        CandidateRule(
            "Venue draw sum 0.35-0.65",
            "hdraw",
            "venue",
            lambda row: row.get("venue_draw_sum") is not None
            and 0.35 <= row["venue_draw_sum"] < 0.65,
        ),
    ]
```

- [ ] **Step 4: Implement rule evaluation**

Add:

```python
def evaluate_rule(rows: list[Row], rule: CandidateRule) -> list[Row]:
    return [row for row in rows if rule.fn(row)]


def candidate_rule_summary(
    rows: list[Row], *, rules: list[CandidateRule], min_bets: int
) -> list[list[Any]]:
    out = []
    for rule in rules:
        selected = evaluate_rule(rows, rule)
        stats = calculate_stats(selected, target=rule.channel)
        if stats.bets >= min_bets:
            out.append(stats_row(rule.name, stats))
    return sorted(out, key=lambda row: (row[4], row[3], row[1]), reverse=True)
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_incremental_signal_validation.py -q
```

Expected: PASS.

## Task 5: Markdown Report Generator

**Files:**
- Modify: `backend/app/scripts/incremental_signal_validation.py`

- [ ] **Step 1: Add Markdown table helpers**

Add:

```python
def markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return lines


def baseline_rows(rows: list[Row]) -> list[list[Any]]:
    return [
        stats_row("draw", calculate_stats(rows, target="draw")),
        stats_row("handicap_draw", calculate_stats(rows, target="hdraw")),
        stats_row("HDRAW_A current", calculate_stats([row for row in rows if is_hdraw_a(row)], target="hdraw")),
    ]


def window_rows(rows: list[Row], *, target: Target, start: date, end: date, days: int) -> list[list[Any]]:
    out = []
    for window_start, window_end in non_overlapping_windows(start, end, days=days):
        stats = window_summary(rows, target=target, start=window_start, end=window_end)
        out.append(stats_row(f"{window_start} 至 {window_end}", stats))
    return out
```

- [ ] **Step 2: Implement report generation**

Add:

```python
def render_report(rows: list[Row], *, start: date, end: date) -> str:
    rows = add_analysis_buckets(rows)
    lines: list[str] = [
        "# V3.1/V4 Incremental Signal Validation",
        "",
        "日期: 2026-04-26",
        f"数据范围: {start.isoformat()} 至 {end.isoformat()}",
        "",
        "## 1. 数据完整性",
        "",
        *markdown_table(["dimension", "coverage", "status"], data_gap_rows(rows)),
        "",
        "## 2. 当前基线",
        "",
        *markdown_table(["target", "bets", "hits", "hit_rate", "roi", "avg_odds"], baseline_rows(rows)),
        "",
        "## 3. Draw Channel 单变量分桶",
        "",
    ]

    for key in [
        "abs_hcap_bucket",
        "rank_gap_bucket",
        "season_draw_sum_bucket",
        "venue_draw_sum_bucket",
        "h2h_draw_rate_bucket",
        "home_recent_win_bucket",
        "away_recent_loss_bucket",
        "league_group",
    ]:
        lines.extend([
            f"### {key}",
            "",
            *markdown_table(
                ["bucket", "bets", "hits", "hit_rate", "roi", "avg_odds"],
                bucket_summary(rows, key=key, target="draw", min_bets=20),
            ),
            "",
        ])

    lines.extend(["## 4. Handicap Draw Channel 单变量分桶", ""])
    for key in [
        "abs_hcap_bucket",
        "rank_gap_bucket",
        "season_draw_sum_bucket",
        "venue_draw_sum_bucket",
        "h2h_draw_rate_bucket",
        "home_recent_win_bucket",
        "away_recent_loss_bucket",
        "league_group",
    ]:
        lines.extend([
            f"### {key}",
            "",
            *markdown_table(
                ["bucket", "bets", "hits", "hit_rate", "roi", "avg_odds"],
                bucket_summary(rows, key=key, target="hdraw", min_bets=20),
            ),
            "",
        ])

    lines.extend([
        "## 5. 候选规则",
        "",
        "### Draw Channel",
        "",
        *markdown_table(
            ["rule", "bets", "hits", "hit_rate", "roi", "avg_odds"],
            candidate_rule_summary(rows, rules=draw_candidate_rules(), min_bets=25),
        ),
        "",
        "### Handicap Draw Channel",
        "",
        *markdown_table(
            ["rule", "bets", "hits", "hit_rate", "roi", "avg_odds"],
            candidate_rule_summary(rows, rules=hdraw_candidate_rules(), min_bets=25),
        ),
        "",
        "## 6. 90 天窗口",
        "",
        "### Draw Channel",
        "",
        *markdown_table(
            ["window", "bets", "hits", "hit_rate", "roi", "avg_odds"],
            window_rows(rows, target="draw", start=start, end=end, days=90),
        ),
        "",
        "### Handicap Draw Channel",
        "",
        *markdown_table(
            ["window", "bets", "hits", "hit_rate", "roi", "avg_odds"],
            window_rows(rows, target="hdraw", start=start, end=end, days=90),
        ),
        "",
        "## 7. 初步结论",
        "",
        "- 本报告只做增量信号验证，不修改模型。",
        "- 若某个维度只有数据缺口，没有稳定历史字段，则不能进入模型。",
        "- 是否进入 V3.1/V4 必须基于本报告和人工复核。",
        "",
    ])
    return "\n".join(lines)
```

- [ ] **Step 3: Add CLI**

Add:

```python
def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2024-09-28")
    parser.add_argument("--end", default="2026-04-22")
    parser.add_argument(
        "--report",
        default="docs/analysis/2026-04-26-v31-v4-incremental-signal-validation.md",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    with SessionLocal() as db:
        rows = load_rows(db, start=start, end=end)
    report = render_report(rows, start=start, end=end)
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    print(f"rows={len(rows)} report={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run lint and tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_incremental_signal_validation.py -q && .venv/bin/python -m ruff check app/scripts/incremental_signal_validation.py tests/test_incremental_signal_validation.py
```

Expected: PASS and `All checks passed!`.

## Task 6: Generate Report Against MySQL

**Files:**
- Create: `docs/analysis/2026-04-26-v31-v4-incremental-signal-validation.md`

- [ ] **Step 1: Run analysis script**

Run:

```bash
MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308 MYSQL_DATABASE=sporttery_10x MYSQL_USER=sporttery MYSQL_PASSWORD=sporttery_pass PYTHONPATH=backend backend/.venv/bin/python -m app.scripts.incremental_signal_validation --start 2024-09-28 --end 2026-04-22 --report docs/analysis/2026-04-26-v31-v4-incremental-signal-validation.md
```

Expected output:

```text
rows=3267 report=docs/analysis/2026-04-26-v31-v4-incremental-signal-validation.md
```

If row count differs, record the actual row count in the final response.

- [ ] **Step 2: Verify report has required sections**

Run:

```bash
rg -n "数据完整性|当前基线|Draw Channel|Handicap Draw Channel|候选规则|90 天窗口|初步结论" docs/analysis/2026-04-26-v31-v4-incremental-signal-validation.md
```

Expected: all section names are found.

- [ ] **Step 3: Verify report has no placeholders**

Run:

```bash
rg -n "TBD|TODO|FIXME|待定|待补充|placeholder|<fill|\.\.\." docs/analysis/2026-04-26-v31-v4-incremental-signal-validation.md
```

Expected: no output.

## Task 7: Interpret The Report Before Any Model Plan

**Files:**
- Modify: `docs/analysis/2026-04-26-v31-v4-incremental-signal-validation.md`

- [ ] **Step 1: Read top candidate sections**

Run:

```bash
sed -n '1,260p' docs/analysis/2026-04-26-v31-v4-incremental-signal-validation.md
```

Expected: report contains data completeness, baselines, and first bucket sections.

- [ ] **Step 2: Add manual interpretation section**

Append to the report:

```markdown
## 8. 人工复核结论

### 8.1 可以继续研究的信号

- 根据上方实际统计填写具体信号名称和原因。

### 8.2 不建议进入模型的信号

- 根据上方实际统计填写具体信号名称和原因。

### 8.3 必须补抓的数据

- 近 5/10 场结构化比分。
- 球队进球/失球统计。
- 一球胜负分布。
- 赔率/盘口变化轨迹。

### 8.4 是否进入 V3.1/V4 实现计划

- 若没有足够证据，结论写“不进入实现计划”。
- 若有足够证据，结论写“先写 V3.1/V4 模型设计文档，不直接改代码”。
```

Replace the two “根据上方实际统计填写” lines with concrete findings from the generated report before completion.

- [ ] **Step 3: Verify interpretation has no generic filler**

Run:

```bash
rg -n "根据上方实际统计填写|待定|待补充|TODO|TBD" docs/analysis/2026-04-26-v31-v4-incremental-signal-validation.md
```

Expected: no output.

## Task 8: Final Verification

**Files:**
- No new source edits unless verification exposes issues.

- [ ] **Step 1: Run targeted tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_incremental_signal_validation.py -q
```

Expected: PASS.

- [ ] **Step 2: Run lint**

Run:

```bash
cd backend && .venv/bin/python -m ruff check app/scripts/incremental_signal_validation.py tests/test_incremental_signal_validation.py
```

Expected: `All checks passed!`.

- [ ] **Step 3: Confirm no model files changed**

Run:

```bash
git diff -- backend/app/engine/scoring.py backend/app/engine/service.py backend/app/scripts/seed.py
```

Expected: no diff from this task. If existing unrelated diff is present, do not revert it; state that this task did not intentionally modify these files.

- [ ] **Step 4: Summarize report conclusion**

Final response must include:

- Row count analyzed.
- Which existing fields were usable.
- Which important fields are missing.
- Whether any signal is strong enough to justify a V3.1/V4 model design.
- Explicit statement that no recommendation model logic was changed.

## Self-Review

Spec coverage:

- Draw and Handicap Draw split: Tasks 3, 4, 5.
- Data gaps: Task 2 and Task 6.
- Incremental signals: Task 4 and Task 5.
- 90-day windows: Task 3 and Task 5.
- No model mutation: File structure and Task 8.
- Report output: Task 6 and Task 7.

Placeholder scan:

- The plan contains no unspecified implementation steps.
- Task 7 includes temporary interpretation prompts, but the same task requires replacing them before completion and verifies with `rg`.

Type consistency:

- `Row` is `dict[str, Any]` throughout.
- `Target` accepts `draw` or `hdraw`.
- `Stats` shape is reused by all summaries.
- CLI report path is a string converted to `Path` before writing.

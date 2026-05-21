# V3.1 组合候选规则回测 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 V3.1 组合候选规则研究模型，写入独立 inactive 模型历史 score，让现有历史回测页面可以直接查看效果，同时生成中文 Markdown 报告和 CSV 明细。

**Architecture:** 在现有 `SportteryMatchScore` 多模型结构上新增 `empirical-v31-combination-candidate` 候选模型配置，`is_active=false`。规则函数、派生字段、组合去重、报告渲染拆成可测试纯函数；脚本只写该候选模型在指定日期范围内的历史 score，不接今日推荐，不改变 active 模型。

**Tech Stack:** Python 3.11/3.12, SQLAlchemy, pytest, ruff, MySQL, Markdown/CSV 输出。

---

## 文件结构

- Create: `backend/app/scripts/v31_combination_candidate_backtest.py`
  - 加载历史样本。
  - 计算 V3.1 派生特征。
  - 定义普通平与让平候选组合规则。
  - 创建或复用 `empirical-v31-combination-candidate`。
  - 写入该候选模型历史 score。
  - 输出 Markdown 报告和 CSV 明细。

- Create: `backend/tests/test_v31_combination_candidate_backtest.py`
  - 覆盖派生字段、规则命中、组合去重、窗口统计、候选模型配置和 score 写入边界。

- Create: `docs/analysis/2026-04-26-v31-combination-candidate-backtest.md`
  - 脚本生成的中文候选回测报告。

- Create: `docs/analysis/v31-combination-candidates.csv`
  - 脚本生成的候选命中明细。

- Read: `docs/superpowers/specs/2026-04-26-v31-combination-candidate-backtest-design.md`
  - 实施前确认范围。

---

## Task 1: 建立测试骨架和规则数据结构

**Files:**
- Create: `backend/tests/test_v31_combination_candidate_backtest.py`
- Create: `backend/app/scripts/v31_combination_candidate_backtest.py`

- [ ] **Step 1: 写失败测试: 候选规则数据结构**

Create `backend/tests/test_v31_combination_candidate_backtest.py`:

```python
from __future__ import annotations

from datetime import date

from app.scripts.v31_combination_candidate_backtest import (
    CandidateRule,
    calculate_stats,
    draw_rules,
    hdraw_rules,
)


def test_candidate_rule_has_required_fields():
    rule = CandidateRule(
        name="DRAW_V31_TEST",
        channel="draw",
        bet_type="draw",
        priority=10,
        fn=lambda row: True,
    )

    assert rule.name == "DRAW_V31_TEST"
    assert rule.channel == "draw"
    assert rule.bet_type == "draw"
    assert rule.priority == 10
    assert rule.fn({}) is True


def test_draw_and_hdraw_rules_are_named_and_prioritized():
    draw_names = [rule.name for rule in draw_rules()]
    hdraw_names = [rule.name for rule in hdraw_rules()]

    assert draw_names == [
        "DRAW_V31_D",
        "DRAW_V31_A",
        "DRAW_V31_B",
        "DRAW_V31_C",
    ]
    assert hdraw_names == [
        "HDRAW_V31_A1",
        "HDRAW_V31_A2",
        "HDRAW_V31_A0",
        "HDRAW_V31_B",
        "HDRAW_V31_C",
    ]
    assert [rule.priority for rule in draw_rules()] == [100, 90, 80, 70]
    assert [rule.priority for rule in hdraw_rules()] == [100, 95, 90, 80, 70]


def test_calculate_stats_uses_fixed_100_stake():
    rows = [
        {"hit": True, "odds": 3.6},
        {"hit": False, "odds": 3.4},
    ]

    stats = calculate_stats(rows)

    assert stats.bets == 2
    assert stats.hits == 1
    assert stats.hit_rate == 0.5
    assert round(stats.roi, 4) == 0.8
    assert stats.pnl == 160.0
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_v31_combination_candidate_backtest.py -q
```

Expected:

```text
FAIL because app.scripts.v31_combination_candidate_backtest does not exist
```

- [ ] **Step 3: 写最小脚本骨架**

Create `backend/app/scripts/v31_combination_candidate_backtest.py`:

```python
"""V3.1 组合候选规则历史 score 生成脚本。"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Literal

Row = dict[str, Any]
Channel = Literal["draw", "hdraw"]


@dataclass(frozen=True)
class Stats:
    bets: int
    hits: int
    hit_rate: float
    pnl: float
    roi: float
    avg_odds: float


@dataclass(frozen=True)
class CandidateRule:
    name: str
    channel: Channel
    bet_type: str
    priority: int
    fn: Callable[[Row], bool]


def calculate_stats(rows: Iterable[Row]) -> Stats:
    usable = [row for row in rows if row.get("odds") is not None]
    bets = len(usable)
    hits = sum(1 for row in usable if row.get("hit") is True)
    pnls = [
        (float(row["odds"]) - 1.0) * 100 if row.get("hit") is True else -100.0
        for row in usable
    ]
    avg_odds = sum(float(row["odds"]) for row in usable) / bets if bets else 0.0
    pnl = sum(pnls)
    roi = pnl / (bets * 100) if bets else 0.0
    return Stats(
        bets=bets,
        hits=hits,
        hit_rate=hits / bets if bets else 0.0,
        pnl=pnl,
        roi=roi,
        avg_odds=avg_odds,
    )


def draw_rules() -> list[CandidateRule]:
    return [
        CandidateRule("DRAW_V31_D", "draw", "draw", 100, lambda row: False),
        CandidateRule("DRAW_V31_A", "draw", "draw", 90, lambda row: False),
        CandidateRule("DRAW_V31_B", "draw", "draw", 80, lambda row: False),
        CandidateRule("DRAW_V31_C", "draw", "draw", 70, lambda row: False),
    ]


def hdraw_rules() -> list[CandidateRule]:
    return [
        CandidateRule("HDRAW_V31_A1", "hdraw", "handicap_draw", 100, lambda row: False),
        CandidateRule("HDRAW_V31_A2", "hdraw", "handicap_draw", 95, lambda row: False),
        CandidateRule("HDRAW_V31_A0", "hdraw", "handicap_draw", 90, lambda row: False),
        CandidateRule("HDRAW_V31_B", "hdraw", "handicap_draw", 80, lambda row: False),
        CandidateRule("HDRAW_V31_C", "hdraw", "handicap_draw", 70, lambda row: False),
    ]
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_v31_combination_candidate_backtest.py -q
```

Expected:

```text
3 passed
```

---

## Task 2: 实现派生字段计算

**Files:**
- Modify: `backend/tests/test_v31_combination_candidate_backtest.py`
- Modify: `backend/app/scripts/v31_combination_candidate_backtest.py`

- [ ] **Step 1: 写失败测试: 派生字段**

Append tests:

```python
from app.scripts.v31_combination_candidate_backtest import enrich_features, safe_rate


def test_safe_rate_handles_missing_and_zero():
    assert safe_rate(None, 6) is None
    assert safe_rate(1, None) is None
    assert safe_rate(1, 0) is None
    assert safe_rate(2, 4) == 0.5


def test_enrich_features_computes_v31_rates():
    row = {
        "home_rank": 4,
        "away_rank": 13,
        "home_season_draws": 5,
        "home_season_wins": 8,
        "home_season_losses": 7,
        "away_season_draws": 4,
        "away_season_wins": 6,
        "away_season_losses": 10,
        "home_home_draws": 3,
        "home_home_wins": 4,
        "home_home_losses": 3,
        "away_away_draws": 2,
        "away_away_wins": 3,
        "away_away_losses": 5,
        "home_recent_form": "WDDLLW",
        "away_recent_form": "LDLDWW",
        "h2h_draws": 2,
        "h2h_home_wins": 2,
        "h2h_away_wins": 1,
        "home_recent_matches_count": 6,
        "home_recent_win_by_1": 2,
        "home_recent_low_scoring_count": 4,
        "away_recent_matches_count": 6,
        "away_recent_loss_by_1": 1,
        "away_recent_loss_by_2plus": 2,
        "away_recent_goals_against": 9,
        "away_recent_low_scoring_count": 3,
        "h2h_matches_count": 5,
        "h2h_one_goal_margin_count": 3,
    }

    out = enrich_features(row)

    assert out["rank_gap"] == 9
    assert out["season_draw_sum"] == 0.45
    assert out["venue_draw_sum"] == 0.5
    assert round(out["recent_draw_sum"], 4) == 0.5
    assert out["h2h_draw_rate"] == 0.4
    assert round(out["home_recent_win_by_1_rate"], 4) == 0.3333
    assert round(out["away_recent_loss_by_1_rate"], 4) == 0.1667
    assert out["away_recent_ga_per_match"] == 1.5
    assert round(out["away_recent_loss_by_2plus_rate"], 4) == 0.3333
    assert out["h2h_one_goal_margin_rate"] == 0.6
    assert round(out["recent_low_scoring_sum"], 4) == 1.1667
```

- [ ] **Step 2: 实现 `safe_rate()` 和 `enrich_features()`**

Add to script:

```python
def safe_rate(numerator: int | float | None, denominator: int | float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def _sum_ints(*values: int | None) -> int:
    return sum(value or 0 for value in values)


def _form_rate(form: str | None, char: str) -> float | None:
    if not form:
        return None
    text = form.upper()
    return text.count(char) / len(text) if text else None


def enrich_features(row: Row) -> Row:
    item = dict(row)
    item["rank_gap"] = (
        abs(item["home_rank"] - item["away_rank"])
        if item.get("home_rank") is not None and item.get("away_rank") is not None
        else None
    )

    home_season_total = _sum_ints(
        item.get("home_season_wins"), item.get("home_season_draws"), item.get("home_season_losses")
    )
    away_season_total = _sum_ints(
        item.get("away_season_wins"), item.get("away_season_draws"), item.get("away_season_losses")
    )
    home_venue_total = _sum_ints(
        item.get("home_home_wins"), item.get("home_home_draws"), item.get("home_home_losses")
    )
    away_venue_total = _sum_ints(
        item.get("away_away_wins"), item.get("away_away_draws"), item.get("away_away_losses")
    )
    h2h_total = _sum_ints(item.get("h2h_home_wins"), item.get("h2h_draws"), item.get("h2h_away_wins"))

    home_season_draw = safe_rate(item.get("home_season_draws"), home_season_total)
    away_season_draw = safe_rate(item.get("away_season_draws"), away_season_total)
    home_venue_draw = safe_rate(item.get("home_home_draws"), home_venue_total)
    away_venue_draw = safe_rate(item.get("away_away_draws"), away_venue_total)
    home_recent_draw = _form_rate(item.get("home_recent_form"), "D")
    away_recent_draw = _form_rate(item.get("away_recent_form"), "D")

    item["season_draw_sum"] = (
        home_season_draw + away_season_draw if home_season_draw is not None and away_season_draw is not None else None
    )
    item["venue_draw_sum"] = (
        home_venue_draw + away_venue_draw if home_venue_draw is not None and away_venue_draw is not None else None
    )
    item["recent_draw_sum"] = (
        home_recent_draw + away_recent_draw if home_recent_draw is not None and away_recent_draw is not None else None
    )
    item["h2h_draw_rate"] = safe_rate(item.get("h2h_draws"), h2h_total)
    item["home_recent_win_by_1_rate"] = safe_rate(
        item.get("home_recent_win_by_1"), item.get("home_recent_matches_count")
    )
    item["away_recent_loss_by_1_rate"] = safe_rate(
        item.get("away_recent_loss_by_1"), item.get("away_recent_matches_count")
    )
    item["away_recent_loss_by_2plus_rate"] = safe_rate(
        item.get("away_recent_loss_by_2plus"), item.get("away_recent_matches_count")
    )
    item["away_recent_ga_per_match"] = safe_rate(
        item.get("away_recent_goals_against"), item.get("away_recent_matches_count")
    )
    item["h2h_one_goal_margin_rate"] = safe_rate(
        item.get("h2h_one_goal_margin_count"), item.get("h2h_matches_count")
    )
    home_low = safe_rate(item.get("home_recent_low_scoring_count"), item.get("home_recent_matches_count"))
    away_low = safe_rate(item.get("away_recent_low_scoring_count"), item.get("away_recent_matches_count"))
    item["recent_low_scoring_sum"] = home_low + away_low if home_low is not None and away_low is not None else None
    return item
```

- [ ] **Step 3: 运行测试**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_v31_combination_candidate_backtest.py -q
```

Expected:

```text
5 passed
```

---

## Task 3: 实现候选组合规则

**Files:**
- Modify: `backend/tests/test_v31_combination_candidate_backtest.py`
- Modify: `backend/app/scripts/v31_combination_candidate_backtest.py`

- [ ] **Step 1: 写失败测试: 普通平规则**

Append tests:

```python
def test_draw_v31_rules_match_expected_rows():
    base = {
        "h2h_draw_rate": 0.4,
        "abs_hcap": 0.5,
        "had_d": 3.3,
        "h2h_one_goal_margin_rate": 0.5,
        "recent_low_scoring_sum": 1.2,
        "recent_draw_sum": 0.6,
    }
    rules = {rule.name: rule for rule in draw_rules()}

    assert rules["DRAW_V31_A"].fn(base) is True
    assert rules["DRAW_V31_B"].fn(base) is True
    assert rules["DRAW_V31_C"].fn(base) is True
    assert rules["DRAW_V31_D"].fn(base) is True
    assert rules["DRAW_V31_A"].fn({**base, "abs_hcap": 1.0}) is False
    assert rules["DRAW_V31_C"].fn({**base, "had_d": 3.8}) is False
```

- [ ] **Step 2: 写失败测试: 让平规则**

Append tests:

```python
def test_hdraw_v31_rules_match_expected_rows():
    base = {
        "abs_hcap": 1.0,
        "rank_gap": 10,
        "hhad_d": 3.6,
        "venue_draw_sum": 0.5,
        "season_draw_sum": 0.45,
        "home_recent_win_by_1_rate": 0.2,
        "away_recent_loss_by_1_rate": 0.2,
        "away_recent_ga_per_match": 1.4,
        "away_recent_loss_by_2plus_rate": 0.2,
    }
    rules = {rule.name: rule for rule in hdraw_rules()}

    assert rules["HDRAW_V31_A0"].fn(base) is True
    assert rules["HDRAW_V31_A1"].fn(base) is True
    assert rules["HDRAW_V31_A2"].fn(base) is True
    assert rules["HDRAW_V31_B"].fn(base) is True
    assert rules["HDRAW_V31_C"].fn({**base, "rank_gap": 17}) is True
    assert rules["HDRAW_V31_A0"].fn({**base, "rank_gap": 3}) is False
    assert rules["HDRAW_V31_A1"].fn({**base, "home_recent_win_by_1_rate": 0.0}) is False
```

- [ ] **Step 3: 实现规则函数**

Replace placeholder lambdas in `draw_rules()` and `hdraw_rules()` with explicit helpers:

```python
def _between(value: float | int | None, low: float, high: float) -> bool:
    return value is not None and low <= float(value) <= high


def _ge(value: float | int | None, threshold: float) -> bool:
    return value is not None and float(value) >= threshold


def _le(value: float | int | None, threshold: float) -> bool:
    return value is not None and float(value) <= threshold


def _hdraw_a0(row: Row) -> bool:
    return (
        _between(row.get("abs_hcap"), 1.00, 1.25)
        and _between(row.get("rank_gap"), 6, 15)
        and _ge(row.get("hhad_d"), 3.50)
        and _ge(row.get("venue_draw_sum"), 0.35)
        and _ge(row.get("season_draw_sum"), 0.35)
    )
```

Then define the rules exactly as the design document states.

- [ ] **Step 4: 运行测试**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_v31_combination_candidate_backtest.py -q
```

Expected:

```text
7 passed
```

---

## Task 4: 实现规则评估、去重和窗口统计

**Files:**
- Modify: `backend/tests/test_v31_combination_candidate_backtest.py`
- Modify: `backend/app/scripts/v31_combination_candidate_backtest.py`

- [ ] **Step 1: 写失败测试: 规则评估**

Append tests:

```python
from app.scripts.v31_combination_candidate_backtest import evaluate_rules, portfolio_rows, window_ranges


def test_evaluate_rules_emits_candidate_rows():
    rows = [
        {
            "match_id": 1,
            "match_date": date(2026, 1, 1),
            "is_draw": True,
            "is_hdraw": False,
            "had_d": 3.3,
            "hhad_d": 3.6,
            "h2h_draw_rate": 0.4,
            "abs_hcap": 0.5,
            "h2h_one_goal_margin_rate": 0.5,
            "recent_low_scoring_sum": 1.2,
            "recent_draw_sum": 0.6,
        }
    ]

    out = evaluate_rules(rows, draw_rules())

    assert {row["rule_name"] for row in out} == {
        "DRAW_V31_A",
        "DRAW_V31_B",
        "DRAW_V31_C",
        "DRAW_V31_D",
    }
    assert all(row["channel"] == "draw" for row in out)
    assert all(row["odds"] == 3.3 for row in out)
    assert all(row["hit"] is True for row in out)


def test_portfolio_rows_keeps_highest_priority_per_channel_match():
    candidates = [
        {"match_id": 1, "channel": "draw", "rule_priority": 70, "rule_name": "DRAW_V31_C"},
        {"match_id": 1, "channel": "draw", "rule_priority": 100, "rule_name": "DRAW_V31_D"},
        {"match_id": 1, "channel": "hdraw", "rule_priority": 90, "rule_name": "HDRAW_V31_A0"},
    ]

    out = portfolio_rows(candidates)

    assert [row["rule_name"] for row in out] == ["DRAW_V31_D", "HDRAW_V31_A0"]


def test_window_ranges_uses_non_overlapping_90_day_windows():
    assert window_ranges(date(2026, 1, 1), date(2026, 4, 10), days=90) == [
        (date(2026, 1, 1), date(2026, 3, 31)),
        (date(2026, 4, 1), date(2026, 4, 10)),
    ]
```

- [ ] **Step 2: 实现评估和窗口函数**

Add:

```python
from datetime import date, timedelta


def _odds_for(row: Row, channel: Channel) -> float | None:
    value = row.get("had_d") if channel == "draw" else row.get("hhad_d")
    return float(value) if value is not None else None


def _hit_for(row: Row, channel: Channel) -> bool:
    return bool(row.get("is_draw")) if channel == "draw" else bool(row.get("is_hdraw"))


def evaluate_rules(rows: list[Row], rules: list[CandidateRule]) -> list[Row]:
    out: list[Row] = []
    for row in rows:
        for rule in rules:
            if not rule.fn(row):
                continue
            odds = _odds_for(row, rule.channel)
            if odds is None:
                continue
            hit = _hit_for(row, rule.channel)
            out.append({
                **row,
                "rule_name": rule.name,
                "rule_priority": rule.priority,
                "channel": rule.channel,
                "bet_type": rule.bet_type,
                "odds": odds,
                "hit": hit,
                "pnl": (odds - 1.0) * 100 if hit else -100.0,
            })
    return out


def portfolio_rows(candidates: list[Row]) -> list[Row]:
    best: dict[tuple[Any, str], Row] = {}
    for row in candidates:
        key = (row["match_id"], row["channel"])
        current = best.get(key)
        if current is None or row["rule_priority"] > current["rule_priority"]:
            best[key] = row
    return sorted(best.values(), key=lambda row: (row["match_id"], row["channel"]))


def window_ranges(start: date, end: date, *, days: int = 90) -> list[tuple[date, date]]:
    windows = []
    cursor = start
    while cursor <= end:
        window_end = min(cursor + timedelta(days=days - 1), end)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return windows
```

- [ ] **Step 3: 运行测试**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_v31_combination_candidate_backtest.py -q
```

Expected:

```text
10 passed
```

---

## Task 5: 实现数据库加载和报告输出

**Files:**
- Modify: `backend/app/scripts/v31_combination_candidate_backtest.py`
- Modify: `backend/tests/test_v31_combination_candidate_backtest.py`

- [ ] **Step 1: 写失败测试: Markdown/CSV 输出纯函数**

Append tests:

```python
from app.scripts.v31_combination_candidate_backtest import csv_lines, render_report


def test_csv_lines_contains_required_columns():
    rows = [{
        "match_id": 1,
        "match_date": date(2026, 1, 1),
        "league": "测试联赛",
        "home_team": "主队",
        "away_team": "客队",
        "rule_name": "DRAW_V31_A",
        "channel": "draw",
        "bet_type": "draw",
        "odds": 3.3,
        "hit": True,
        "pnl": 230.0,
        "abs_hcap": 0.5,
        "rank_gap": 4,
        "had_d": 3.3,
        "hhad_d": 3.6,
        "home_recent_win_by_1_rate": 0.2,
        "away_recent_loss_by_1_rate": 0.2,
        "away_recent_ga_per_match": 1.4,
        "h2h_draw_rate": 0.4,
        "h2h_one_goal_margin_rate": 0.5,
        "recent_low_scoring_sum": 1.2,
    }]

    text = "\n".join(csv_lines(rows))

    assert "match_id,match_date,league,home_team,away_team" in text
    assert "DRAW_V31_A" in text


def test_render_report_contains_required_sections():
    report = render_report(
        rows=[],
        candidates=[],
        portfolio=[],
        start=date(2024, 9, 28),
        end=date(2026, 4, 22),
        detail_path="docs/analysis/v31-combination-candidates.csv",
        write_summary={
            "model_config_id": 9,
            "scored_matches": 0,
            "recommended_scores": 0,
            "draw_scores": 0,
            "handicap_draw_scores": 0,
            "replaced_old_scores": 0,
        },
    )

    assert "# V3.1 组合候选规则回测报告" in report
    assert "## 1. 数据范围" in report
    assert "## 4. 候选规则独立表现" in report
    assert "## 6. 结论" in report
```

- [ ] **Step 2: 实现 `load_rows()`**

Use existing model imports and `_pick_odds` pattern from `incremental_signal_validation.py`:

```python
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.engine.service import _pick_odds
from app.models import League, SportteryMatch, SportteryMatchResult, SportteryMatchTeamStats


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
        row = {
            "match_id": match.id,
            "match_date": match.match_date.date(),
            "league": league.name,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "is_draw": result.result == "draw",
            "is_hdraw": result.handicap_result == "draw",
            "had_d": _float(match.had_d),
            "hhad_d": _float(match.hhad_d),
            "abs_hcap": abs(_float(odds.handicap_value)) if odds.handicap_value is not None else None,
            "hcap": _float(odds.handicap_value),
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
            "home_recent_matches_count": stats.home_recent_matches_count,
            "home_recent_win_by_1": stats.home_recent_win_by_1,
            "home_recent_low_scoring_count": stats.home_recent_low_scoring_count,
            "away_recent_matches_count": stats.away_recent_matches_count,
            "away_recent_loss_by_1": stats.away_recent_loss_by_1,
            "away_recent_loss_by_2plus": stats.away_recent_loss_by_2plus,
            "away_recent_goals_against": stats.away_recent_goals_against,
            "away_recent_low_scoring_count": stats.away_recent_low_scoring_count,
            "h2h_matches_count": stats.h2h_matches_count,
            "h2h_one_goal_margin_count": stats.h2h_one_goal_margin_count,
        }
        rows.append(enrich_features(row))
    return rows
```

- [ ] **Step 3: 实现报告和 CSV 函数**

Add:

```python
def _fmt_pct(value: float) -> str:
    return f"{value:.2%}"


def _fmt_float(value: float) -> str:
    return f"{value:.2f}"


def markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return lines


def stats_row(label: str, rows: list[Row]) -> list[Any]:
    stats = calculate_stats(rows)
    return [label, stats.bets, stats.hits, _fmt_pct(stats.hit_rate), _fmt_pct(stats.roi), _fmt_float(stats.avg_odds), _fmt_float(stats.pnl)]
```

Implement grouping by `rule_name`, by channel portfolio, and by 90-day windows.

- [ ] **Step 4: 写失败测试: 候选模型配置和 score 映射**

Append tests:

```python
from decimal import Decimal

from app.scripts.v31_combination_candidate_backtest import score_values_for_rule


def test_score_values_for_rule_maps_priority_to_display_score():
    assert score_values_for_rule("HDRAW_V31_A1") == (116, Decimal("0.0150"))
    assert score_values_for_rule("HDRAW_V31_A0") == (112, Decimal("0.0120"))
    assert score_values_for_rule("HDRAW_V31_B") == (108, Decimal("0.0100"))
    assert score_values_for_rule("HDRAW_V31_C") == (104, Decimal("0.0080"))
    assert score_values_for_rule("DRAW_V31_D") == (106, Decimal("0.0080"))
    assert score_values_for_rule("DRAW_V31_A") == (102, Decimal("0.0060"))
```

- [ ] **Step 5: 实现候选模型配置和 score 写入函数**

Add:

```python
from decimal import Decimal

from sqlalchemy import and_, delete

from app.models import ModelConfig, SportteryMatchScore

CANDIDATE_MODEL_NAME = "empirical-v31-combination-candidate"


def ensure_candidate_model_config(db: Session) -> ModelConfig:
    existing = db.query(ModelConfig).filter(ModelConfig.name == CANDIDATE_MODEL_NAME).one_or_none()
    if existing is not None:
        if existing.is_active:
            existing.is_active = False
            db.commit()
            db.refresh(existing)
        return existing

    cfg = ModelConfig(
        name=CANDIDATE_MODEL_NAME,
        created_by=None,
        weights_json={
            "euro": 1,
            "asian": 1,
            "goals": 1,
            "intent": 1,
            "compression": 1,
            "team_stats": 1,
        },
        thresholds_json={
            "strategy": "empirical_v31_combination",
            "recommend_total_score": 100,
            "draw_min_score": 100,
            "handicap_draw_min_score": 100,
        },
        kelly_bands_json={
            "research_low": {"min_score": 100, "max_score": 107, "kelly_pct": 0.006},
            "research_mid": {"min_score": 108, "max_score": 113, "kelly_pct": 0.010},
            "research_high": {"min_score": 114, "max_score": 120, "kelly_pct": 0.015},
        },
        scrape_schedule_json=None,
        is_active=False,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def score_values_for_rule(rule_name: str) -> tuple[int, Decimal]:
    if rule_name in {"HDRAW_V31_A1", "HDRAW_V31_A2"}:
        return 116, Decimal("0.0150")
    if rule_name == "HDRAW_V31_A0":
        return 112, Decimal("0.0120")
    if rule_name == "HDRAW_V31_B":
        return 108, Decimal("0.0100")
    if rule_name == "HDRAW_V31_C":
        return 104, Decimal("0.0080")
    if rule_name == "DRAW_V31_D":
        return 106, Decimal("0.0080")
    return 102, Decimal("0.0060")
```

Implement `write_scores()`:

```python
def write_scores(
    db: Session,
    portfolio: list[Row],
    *,
    model_config_id: int,
    start: date,
    end: date,
    replace: bool,
) -> dict[str, int]:
    replaced = 0
    if replace:
        start_key = int(f"{start:%Y%m%d}") * 10000
        end_key = int(f"{end:%Y%m%d}") * 10000 + 9999
        result = db.execute(
            delete(SportteryMatchScore).where(
                and_(
                    SportteryMatchScore.model_config_id == model_config_id,
                    SportteryMatchScore.match_id >= start_key,
                    SportteryMatchScore.match_id <= end_key,
                )
            )
        )
        replaced = result.rowcount or 0

    recommended = draw_scores = hdraw_scores = 0
    for row in portfolio:
        total_score, kelly_pct = score_values_for_rule(row["rule_name"])
        existing = (
            db.query(SportteryMatchScore)
            .filter(
                SportteryMatchScore.match_id == row["match_id"],
                SportteryMatchScore.model_config_id == model_config_id,
            )
            .one_or_none()
        )
        if existing is None:
            existing = SportteryMatchScore(
                match_id=row["match_id"],
                model_config_id=model_config_id,
                user_id=None,
            )
            db.add(existing)
        existing.euro_score = 0
        existing.asian_score = 0
        existing.goals_score = 0
        existing.intent_score = 0
        existing.compression_score = 0
        existing.team_stats_score = total_score
        existing.total_score = total_score
        existing.bet_type = row["bet_type"]
        existing.kelly_pct = kelly_pct
        existing.is_recommended = True
        existing.actual_hit = row["hit"]
        existing.notes = (
            f"V3.1 candidate only; rule={row['rule_name']}; "
            f"rank_gap={row.get('rank_gap')}; abs_hcap={row.get('abs_hcap')}"
        )
        recommended += 1
        if row["bet_type"] == "draw":
            draw_scores += 1
        elif row["bet_type"] == "handicap_draw":
            hdraw_scores += 1

    db.commit()
    return {
        "model_config_id": model_config_id,
        "scored_matches": len(portfolio),
        "recommended_scores": recommended,
        "draw_scores": draw_scores,
        "handicap_draw_scores": hdraw_scores,
        "replaced_old_scores": replaced,
    }
```

- [ ] **Step 6: 实现 CLI**

Add:

```python
import argparse


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2024-09-28")
    parser.add_argument("--end", default="2026-04-22")
    parser.add_argument("--report", default="docs/analysis/2026-04-26-v31-combination-candidate-backtest.md")
    parser.add_argument("--csv", default="docs/analysis/v31-combination-candidates.csv")
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    with SessionLocal() as db:
        rows = load_rows(db, start=start, end=end)
    candidates = evaluate_rules(rows, [*draw_rules(), *hdraw_rules()])
    portfolio = portfolio_rows(candidates)
    with SessionLocal() as db:
        cfg = ensure_candidate_model_config(db)
        write_summary = write_scores(
            db,
            portfolio,
            model_config_id=cfg.id,
            start=start,
            end=end,
            replace=args.replace,
        )

    csv_path = Path(args.csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text("\n".join(csv_lines(candidates)), encoding="utf-8")

    report = render_report(
        rows=rows,
        candidates=candidates,
        portfolio=portfolio,
        start=start,
        end=end,
        detail_path=str(csv_path),
        write_summary=write_summary,
    )
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(
        f"rows={len(rows)} candidates={len(candidates)} portfolio={len(portfolio)} "
        f"scored={write_summary['scored_matches']} model_config_id={write_summary['model_config_id']} "
        f"report={report_path} csv={csv_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: 运行测试**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_v31_combination_candidate_backtest.py -q
```

Expected:

```text
13 passed
```

---

## Task 6: 写入候选模型历史 score 并验收回测入口

**Files:**
- Create: `docs/analysis/2026-04-26-v31-combination-candidate-backtest.md`
- Create: `docs/analysis/v31-combination-candidates.csv`

- [ ] **Step 1: 运行 ruff**

Run:

```bash
cd backend && .venv/bin/python -m ruff check app/scripts/v31_combination_candidate_backtest.py tests/test_v31_combination_candidate_backtest.py
```

Expected:

```text
All checks passed!
```

- [ ] **Step 2: 运行候选回测脚本**

Run:

```bash
MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308 MYSQL_DATABASE=sporttery_10x MYSQL_USER=sporttery MYSQL_PASSWORD=sporttery_pass PYTHONPATH=backend backend/.venv/bin/python -m app.scripts.v31_combination_candidate_backtest --start 2024-09-28 --end 2026-04-22 --report docs/analysis/2026-04-26-v31-combination-candidate-backtest.md --csv docs/analysis/v31-combination-candidates.csv
```

Expected:

```text
rows=<历史样本数> candidates=<候选命中数> portfolio=<去重命中数> scored=<写入score数> model_config_id=<候选模型ID> report=docs/analysis/2026-04-26-v31-combination-candidate-backtest.md csv=docs/analysis/v31-combination-candidates.csv
```

- [ ] **Step 3: 验证只写候选模型 score**

Run:

```bash
docker compose exec mysql mysql --default-character-set=utf8mb4 -uroot -prootpass sporttery_10x -e "select id,name,is_active,JSON_EXTRACT(thresholds_json,'$.strategy') strategy from model_configs where name='empirical-v31-combination-candidate'; select count(*) scores,sum(is_recommended=1) recommended,sum(bet_type='draw') draw_scores,sum(bet_type='handicap_draw') hdraw_scores from sporttery_match_scores where model_config_id=(select id from model_configs where name='empirical-v31-combination-candidate');"
```

Expected:

```text
候选模型存在，is_active=0，strategy=empirical_v31_combination；该模型存在历史 score，且只统计该模型的 score。
```

- [ ] **Step 4: 快速阅读报告结论**

Run:

```bash
sed -n '1,220p' docs/analysis/2026-04-26-v31-combination-candidate-backtest.md
```

Expected:

```text
报告包含数据范围、候选规则独立表现、组合去重表现、90天窗口和结论
```

- [ ] **Step 5: 最终验证**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_v31_combination_candidate_backtest.py tests/test_incremental_signal_validation.py -q
cd backend && .venv/bin/python -m ruff check app/scripts/v31_combination_candidate_backtest.py tests/test_v31_combination_candidate_backtest.py
```

Expected:

```text
pytest PASS
ruff PASS
```

---

## 验收标准

- [ ] 生成 V3.1 候选组合回测报告。
- [ ] 生成候选命中 CSV 明细。
- [ ] 普通平和让平分通道统计。
- [ ] 每条规则独立统计和组合去重统计都存在。
- [ ] 90 天窗口统计存在。
- [ ] 已写入 `empirical-v31-combination-candidate` 对应历史 score。
- [ ] 新增或复用候选模型配置，且 `is_active=false`。
- [ ] 未接今日推荐。
- [ ] 测试和 ruff 通过。

## 自检

- 文档为中文。
- 不包含占位项。
- 实施计划是候选模型历史回测-only。
- 不改变 active 模型，不接今日推荐。

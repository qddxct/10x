# V3.3 单场因子诊断与二串一可行性评估 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 V3.3 研究工作台：基于 V3.2 候选池生成单场因子诊断、二串一组合模拟、随机/约束随机对照，并把报告写入结构化表、Markdown 和 CSV，供页面展示。

**Architecture:** 新增 `backend/app/research/` 研究模块，按 `factors`、`combo`、`random_baseline`、`reporting`、`repository` 分层。新增 `model_research_runs` 与 `model_research_artifacts` 存结构化研究结果；CLI 脚本只做编排，不承载算法。前端先在回测页增加研究报告摘要入口，不改今日推荐和 active 模型。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + MySQL；pytest + ruff；Next.js React 前端。

---

## 0. 文件结构

新增文件：

- `backend/alembic/versions/0012_add_model_research_tables.py`：新增研究运行和研究产物表。
- `backend/app/models/research.py`：SQLAlchemy 模型。
- `backend/app/research/__init__.py`：研究模块导出。
- `backend/app/research/types.py`：研究数据类型、统计结构、枚举常量。
- `backend/app/research/metrics.py`：命中率、ROI、连续不中、百分位等纯函数。
- `backend/app/research/factors.py`：单场因子分层统计。
- `backend/app/research/combo.py`：二串一组单与组合回测。
- `backend/app/research/random_baseline.py`：随机组和约束随机组。
- `backend/app/research/repository.py`：从 DB 加载 V3.2 候选和写入研究表。
- `backend/app/research/reporting.py`：Markdown/CSV/DB artifact 输出。
- `backend/app/scripts/v33_research.py`：CLI 编排入口。
- `backend/app/api/research.py`：研究报告 API。
- `backend/schemas/research.py`：API response schema。
- `backend/tests/test_research_metrics.py`：纯指标测试。
- `backend/tests/test_research_factors.py`：因子分层测试。
- `backend/tests/test_research_combo.py`：二串一测试。
- `backend/tests/test_research_random_baseline.py`：随机对照测试。
- `backend/tests/test_research_reporting.py`：报告输出测试。
- `frontend/lib/research/types.ts`：前端类型。
- `frontend/lib/research/api.ts`：研究报告 API client。
- `frontend/app/backtest/research-summary.tsx`：回测页研究摘要组件。
- `frontend/tests/research-api.test.ts`：前端 API 测试。
- `frontend/tests/research-summary.test.tsx`：摘要组件测试。

修改文件：

- `backend/app/models/__init__.py`：导出研究模型。
- `backend/app/main.py`：挂载 `/api/research`。
- `frontend/app/backtest/backtest-client.tsx`：加载研究摘要并展示入口。
- `docs/analysis/MODEL_RESEARCH_INDEX.md`：实现完成后更新 V3.3 状态和报告路径。

不自动提交：当前 worktree 已有大量未提交变更，本计划不执行 `git commit`，只通过测试和 diff 核验。

---

## Task 1: 研究表结构

**Files:**
- Create: `backend/alembic/versions/0012_add_model_research_tables.py`
- Create: `backend/app/models/research.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 编写迁移文件**

创建 `backend/alembic/versions/0012_add_model_research_tables.py`：

```python
"""add model research run/artifact tables

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-26 14:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_research_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=96), nullable=False),
        sa.Column("base_model_config_id", sa.Integer(), nullable=True),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=False),
        sa.Column("random_trials", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("running", "succeeded", "failed", name="model_research_status"),
            nullable=False,
            server_default="running",
        ),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("report_path", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["base_model_config_id"], ["model_configs.id"], ondelete="SET NULL"),
        comment="模型研究运行记录",
    )
    op.create_index("ix_model_research_runs_name", "model_research_runs", ["name"])
    op.create_index("ix_model_research_runs_created_at", "model_research_runs", ["created_at"])

    op.create_table(
        "model_research_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column(
            "artifact_type",
            sa.Enum(
                "factor_bucket",
                "combo_simulation",
                "random_baseline",
                "window_summary",
                "markdown_report",
                name="model_research_artifact_type",
            ),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["model_research_runs.id"], ondelete="CASCADE"),
        comment="模型研究结构化产物",
    )
    op.create_index("ix_model_research_artifacts_run_type", "model_research_artifacts", ["run_id", "artifact_type"])


def downgrade() -> None:
    op.drop_index("ix_model_research_artifacts_run_type", table_name="model_research_artifacts")
    op.drop_table("model_research_artifacts")
    op.drop_index("ix_model_research_runs_created_at", table_name="model_research_runs")
    op.drop_index("ix_model_research_runs_name", table_name="model_research_runs")
    op.drop_table("model_research_runs")
    sa.Enum(name="model_research_artifact_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="model_research_status").drop(op.get_bind(), checkfirst=True)
```

- [ ] **Step 2: 编写模型文件**

创建 `backend/app/models/research.py`：

```python
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.model_config import ModelConfig


class ModelResearchRun(Base, TimestampMixin):
    """模型研究运行记录。"""

    __tablename__ = "model_research_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    base_model_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    random_trials: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("running", "succeeded", "failed", name="model_research_status"),
        nullable=False,
        default="running",
    )
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    base_model_config: Mapped[ModelConfig | None] = relationship()
    artifacts: Mapped[list[ModelResearchArtifact]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ModelResearchArtifact(Base):
    """模型研究结构化产物。"""

    __tablename__ = "model_research_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("model_research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(
        Enum(
            "factor_bucket",
            "combo_simulation",
            "random_baseline",
            "window_summary",
            "markdown_report",
            name="model_research_artifact_type",
        ),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    run: Mapped[ModelResearchRun] = relationship(back_populates="artifacts")
```

- [ ] **Step 3: 导出模型**

在 `backend/app/models/__init__.py` 增加：

```python
from app.models.research import ModelResearchArtifact, ModelResearchRun
```

并在 `__all__` 增加：

```python
"ModelResearchArtifact",
"ModelResearchRun",
```

- [ ] **Step 4: 运行迁移验证**

Run:

```bash
cd backend && .venv/bin/alembic upgrade head
```

Expected:

```text
Running upgrade 0011 -> 0012, add model research run/artifact tables
```

---

## Task 2: 研究基础类型和指标纯函数

**Files:**
- Create: `backend/app/research/__init__.py`
- Create: `backend/app/research/types.py`
- Create: `backend/app/research/metrics.py`
- Test: `backend/tests/test_research_metrics.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_research_metrics.py`：

```python
from app.research.metrics import max_losing_streak, percentile_rank, summarize_returns


def test_summarize_returns_calculates_roi_and_hit_rate():
    summary = summarize_returns([260.0, -100.0, -100.0], stake=100.0)
    assert summary["bets"] == 3
    assert summary["hits"] == 1
    assert summary["hit_rate"] == 1 / 3
    assert summary["pnl"] == 60.0
    assert summary["roi"] == 0.2


def test_max_losing_streak_counts_consecutive_misses():
    assert max_losing_streak([False, False, True, False, False, False]) == 3
    assert max_losing_streak([True, True]) == 0


def test_percentile_rank_uses_less_or_equal_position():
    assert percentile_rank(5.0, [1.0, 3.0, 5.0, 7.0]) == 0.75
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_metrics.py -q
```

Expected: FAIL，提示 `No module named 'app.research'`。

- [ ] **Step 3: 实现类型和指标**

创建 `backend/app/research/__init__.py`：

```python
"""Research utilities for model diagnostics and combo simulations."""
```

创建 `backend/app/research/types.py`：

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

BetType = Literal["draw", "handicap_draw"]
ComboStrategy = Literal["same_day_strongest", "two_day_rolling", "high_odds_attractor"]


@dataclass(frozen=True)
class ResearchCandidate:
    match_id: int
    match_date: date
    league: str
    home_team: str
    away_team: str
    bet_type: BetType
    odds: float
    is_hit: bool
    total_score: int
    handicap_value: float | None
    had_d: float | None
    hhad_d: float | None
    abs_hcap: float | None
    rank_gap: float | None
    recent_draw_sum: float | None
    recent_low_scoring_sum: float | None
    h2h_draw_rate: float | None
    h2h_one_goal_margin_rate: float | None
    home_recent_goal_diff: float | None
    away_recent_goal_diff: float | None


@dataclass(frozen=True)
class ComboTicket:
    strategy: ComboStrategy
    ticket_date: date
    legs: tuple[ResearchCandidate, ResearchCandidate]
    combo_odds: float
    is_hit: bool
    pnl: float
```

创建 `backend/app/research/metrics.py`：

```python
from __future__ import annotations


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def summarize_returns(pnls: list[float], *, stake: float) -> dict[str, float | int]:
    bets = len(pnls)
    hits = sum(1 for pnl in pnls if pnl > 0)
    total_pnl = round(sum(pnls), 4)
    return {
        "bets": bets,
        "hits": hits,
        "hit_rate": safe_div(hits, bets),
        "pnl": total_pnl,
        "roi": safe_div(total_pnl, bets * stake),
    }


def max_losing_streak(results: list[bool]) -> int:
    current = 0
    longest = 0
    for hit in results:
        if hit:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return longest


def percentile_rank(value: float, samples: list[float]) -> float:
    if not samples:
        return 0.0
    return sum(1 for sample in samples if sample <= value) / len(samples)


def quantile(samples: list[float], q: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return ordered[idx]
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_metrics.py -q
```

Expected: `3 passed`。

---

## Task 3: 单场因子分层统计

**Files:**
- Create: `backend/app/research/factors.py`
- Test: `backend/tests/test_research_factors.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_research_factors.py`：

```python
from datetime import date

from app.research.factors import build_factor_buckets
from app.research.types import ResearchCandidate


def _candidate(**overrides):
    base = dict(
        match_id=1,
        match_date=date(2026, 4, 1),
        league="英超",
        home_team="A",
        away_team="B",
        bet_type="draw",
        odds=3.2,
        is_hit=True,
        total_score=108,
        handicap_value=0.25,
        had_d=3.2,
        hhad_d=None,
        abs_hcap=0.25,
        rank_gap=3,
        recent_draw_sum=0.6,
        recent_low_scoring_sum=1.2,
        h2h_draw_rate=0.4,
        h2h_one_goal_margin_rate=0.5,
        home_recent_goal_diff=2,
        away_recent_goal_diff=-1,
    )
    base.update(overrides)
    return ResearchCandidate(**base)


def test_build_factor_buckets_splits_draw_odds_ranges():
    rows = [
        _candidate(match_id=1, odds=3.2, had_d=3.2, is_hit=True),
        _candidate(match_id=2, odds=3.55, had_d=3.55, is_hit=False),
    ]
    buckets = build_factor_buckets(rows)
    by_label = {b["label"]: b for b in buckets if b["factor"] == "draw_odds_range"}
    assert by_label["3.10-3.29"]["bets"] == 1
    assert by_label["3.10-3.29"]["roi"] == 2.2
    assert by_label["3.50+"]["bets"] == 1
    assert by_label["3.50+"]["roi"] == -1.0


def test_build_factor_buckets_marks_small_sample_observational():
    buckets = build_factor_buckets([_candidate(match_id=1)])
    first = next(b for b in buckets if b["factor"] == "league")
    assert first["sample_note"] == "观察样本"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_factors.py -q
```

Expected: FAIL，提示 `No module named 'app.research.factors'`。

- [ ] **Step 3: 实现 factors**

创建 `backend/app/research/factors.py`：

```python
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable

from app.research.metrics import max_losing_streak, summarize_returns
from app.research.types import ResearchCandidate

BucketFn = Callable[[ResearchCandidate], str]


def _range(value: float | None, ranges: list[tuple[float, float | None, str]]) -> str:
    if value is None:
        return "未知"
    for low, high, label in ranges:
        if high is None and value >= low:
            return label
        if high is not None and low <= value <= high:
            return label
    return "其他"


def _direction(value: float | None, positive_label: str, negative_label: str) -> str:
    if value is None:
        return "未知"
    if value > 0:
        return positive_label
    if value < 0:
        return negative_label
    return "均势"


FACTOR_DEFS: list[tuple[str, BucketFn]] = [
    ("league", lambda c: c.league),
    ("draw_odds_range", lambda c: _range(c.had_d, [(3.10, 3.29, "3.10-3.29"), (3.30, 3.49, "3.30-3.49"), (3.50, None, "3.50+")])),
    ("handicap_draw_odds_range", lambda c: _range(c.hhad_d, [(3.10, 3.39, "3.10-3.39"), (3.40, 3.69, "3.40-3.69"), (3.70, None, "3.70+")])),
    ("abs_hcap_range", lambda c: _range(c.abs_hcap, [(0.0, 0.0, "0"), (0.25, 0.25, "0.25"), (0.50, 0.50, "0.50"), (0.75, None, "0.75+")])),
    ("rank_gap_range", lambda c: _range(c.rank_gap, [(0, 4, "0-4"), (5, 9, "5-9"), (10, None, "10+")])),
    ("recent_draw_sum", lambda c: _range(c.recent_draw_sum, [(0, 0.49, "低"), (0.50, 0.79, "中"), (0.80, None, "高")])),
    ("recent_low_scoring_sum", lambda c: _range(c.recent_low_scoring_sum, [(0, 0.99, "低"), (1.00, 1.39, "中"), (1.40, None, "高")])),
    ("h2h_draw_rate", lambda c: _range(c.h2h_draw_rate, [(0, 0.24, "低"), (0.25, 0.34, "中"), (0.35, None, "高")])),
    ("h2h_one_goal_margin_rate", lambda c: _range(c.h2h_one_goal_margin_rate, [(0, 0.24, "低"), (0.25, 0.34, "中"), (0.35, None, "高")])),
    ("home_recent_goal_diff", lambda c: _direction(c.home_recent_goal_diff, "主队强", "主队弱")),
    ("away_recent_goal_diff", lambda c: _direction(c.away_recent_goal_diff, "客队强", "客队弱")),
]


def build_factor_buckets(candidates: Iterable[ResearchCandidate], *, stake: float = 100.0) -> list[dict]:
    rows = list(candidates)
    out: list[dict] = []
    for factor, bucket_fn in FACTOR_DEFS:
        grouped: dict[str, list[ResearchCandidate]] = defaultdict(list)
        for candidate in rows:
            grouped[bucket_fn(candidate)].append(candidate)
        for label, items in sorted(grouped.items()):
            pnls = [(item.odds - 1) * stake if item.is_hit else -stake for item in items]
            summary = summarize_returns(pnls, stake=stake)
            out.append(
                {
                    "factor": factor,
                    "label": label,
                    "bets": summary["bets"],
                    "hits": summary["hits"],
                    "hit_rate": summary["hit_rate"],
                    "avg_odds": sum(item.odds for item in items) / len(items),
                    "pnl": summary["pnl"],
                    "roi": summary["roi"],
                    "max_losing_streak": max_losing_streak([item.is_hit for item in items]),
                    "sample_note": "可参考" if len(items) >= 30 else "观察样本",
                }
            )
    return out
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_factors.py -q
```

Expected: `2 passed`。

---

## Task 4: 二串一组单模拟

**Files:**
- Create: `backend/app/research/combo.py`
- Test: `backend/tests/test_research_combo.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_research_combo.py`：

```python
from datetime import date, timedelta

from app.research.combo import simulate_combo_strategy, summarize_combo_tickets
from app.research.types import ResearchCandidate


def _candidate(match_id: int, day: date, *, bet_type="draw", odds=3.0, hit=True, score=108):
    return ResearchCandidate(
        match_id=match_id,
        match_date=day,
        league="英超",
        home_team=f"H{match_id}",
        away_team=f"A{match_id}",
        bet_type=bet_type,
        odds=odds,
        is_hit=hit,
        total_score=score,
        handicap_value=1.0 if bet_type == "handicap_draw" else 0.25,
        had_d=odds if bet_type == "draw" else None,
        hhad_d=odds if bet_type == "handicap_draw" else None,
        abs_hcap=0.25,
        rank_gap=5,
        recent_draw_sum=0.6,
        recent_low_scoring_sum=1.2,
        h2h_draw_rate=0.4,
        h2h_one_goal_margin_rate=0.4,
        home_recent_goal_diff=1,
        away_recent_goal_diff=-1,
    )


def test_same_day_strongest_builds_one_ticket_per_day():
    day = date(2026, 4, 1)
    tickets = simulate_combo_strategy(
        [_candidate(1, day, odds=3.0), _candidate(2, day, odds=3.5, hit=False), _candidate(3, day, odds=3.2)],
        strategy="same_day_strongest",
    )
    assert len(tickets) == 1
    assert tickets[0].combo_odds == 9.6
    assert tickets[0].is_hit is True
    assert tickets[0].pnl == 860.0


def test_two_day_rolling_pairs_across_adjacent_days():
    day = date(2026, 4, 1)
    tickets = simulate_combo_strategy(
        [_candidate(1, day), _candidate(2, day + timedelta(days=1))],
        strategy="two_day_rolling",
    )
    assert len(tickets) == 1
    assert tickets[0].ticket_date == day


def test_summarize_combo_tickets_reports_frequency():
    day = date(2026, 4, 1)
    tickets = simulate_combo_strategy([_candidate(1, day), _candidate(2, day)], strategy="same_day_strongest")
    summary = summarize_combo_tickets(tickets, total_days=10)
    assert summary["combo_count"] == 1
    assert summary["coverage_rate"] == 0.1
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_combo.py -q
```

Expected: FAIL，提示 `No module named 'app.research.combo'`。

- [ ] **Step 3: 实现 combo**

创建 `backend/app/research/combo.py`：

```python
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from itertools import combinations

from app.research.metrics import max_losing_streak, summarize_returns
from app.research.types import ComboStrategy, ComboTicket, ResearchCandidate


def _strength(candidate: ResearchCandidate, *, high_odds: bool = False) -> tuple[float, float, float]:
    type_bonus = 8.0 if candidate.bet_type == "handicap_draw" else 0.0
    odds_bonus = candidate.odds if high_odds else 0.0
    return (candidate.total_score + type_bonus, odds_bonus, candidate.odds)


def _best_pair(candidates: list[ResearchCandidate], *, high_odds: bool) -> tuple[ResearchCandidate, ResearchCandidate] | None:
    if len(candidates) < 2:
        return None
    ordered = sorted(candidates, key=lambda c: _strength(c, high_odds=high_odds), reverse=True)
    return ordered[0], ordered[1]


def _ticket(strategy: ComboStrategy, ticket_date: date, a: ResearchCandidate, b: ResearchCandidate, *, stake: float) -> ComboTicket:
    combo_odds = round(a.odds * b.odds, 4)
    hit = a.is_hit and b.is_hit
    pnl = round((combo_odds - 1) * stake if hit else -stake, 4)
    return ComboTicket(strategy=strategy, ticket_date=ticket_date, legs=(a, b), combo_odds=combo_odds, is_hit=hit, pnl=pnl)


def simulate_combo_strategy(
    candidates: list[ResearchCandidate],
    *,
    strategy: ComboStrategy,
    stake: float = 100.0,
) -> list[ComboTicket]:
    by_date: dict[date, list[ResearchCandidate]] = defaultdict(list)
    for candidate in candidates:
        by_date[candidate.match_date].append(candidate)

    tickets: list[ComboTicket] = []
    used_match_ids: set[int] = set()
    high_odds = strategy == "high_odds_attractor"

    if strategy in {"same_day_strongest", "high_odds_attractor"}:
        for day in sorted(by_date):
            pair = _best_pair(by_date[day], high_odds=high_odds)
            if pair is not None:
                tickets.append(_ticket(strategy, day, pair[0], pair[1], stake=stake))
        return tickets

    if strategy == "two_day_rolling":
        for day in sorted(by_date):
            window = [
                c
                for c in by_date.get(day, []) + by_date.get(day + timedelta(days=1), [])
                if c.match_id not in used_match_ids
            ]
            pair = _best_pair(window, high_odds=False)
            if pair is None:
                continue
            used_match_ids.update({pair[0].match_id, pair[1].match_id})
            tickets.append(_ticket(strategy, day, pair[0], pair[1], stake=stake))
        return tickets

    raise ValueError(f"unsupported combo strategy: {strategy}")


def summarize_combo_tickets(tickets: list[ComboTicket], *, total_days: int, stake: float = 100.0) -> dict:
    pnls = [ticket.pnl for ticket in tickets]
    summary = summarize_returns(pnls, stake=stake)
    combo_odds = [ticket.combo_odds for ticket in tickets]
    return {
        "combo_count": summary["bets"],
        "hit_count": summary["hits"],
        "hit_rate": summary["hit_rate"],
        "roi": summary["roi"],
        "pnl": summary["pnl"],
        "avg_combo_odds": sum(combo_odds) / len(combo_odds) if combo_odds else 0.0,
        "median_combo_odds": sorted(combo_odds)[len(combo_odds) // 2] if combo_odds else 0.0,
        "active_days": len({ticket.ticket_date for ticket in tickets}),
        "coverage_rate": len({ticket.ticket_date for ticket in tickets}) / total_days if total_days else 0.0,
        "max_losing_streak": max_losing_streak([ticket.is_hit for ticket in tickets]),
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_combo.py -q
```

Expected: `3 passed`。

---

## Task 5: 随机对照组

**Files:**
- Create: `backend/app/research/random_baseline.py`
- Test: `backend/tests/test_research_random_baseline.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_research_random_baseline.py`：

```python
from datetime import date

from app.research.random_baseline import run_random_combo_baseline
from app.research.types import ResearchCandidate


def _candidate(match_id: int, odds: float, hit: bool):
    return ResearchCandidate(
        match_id=match_id,
        match_date=date(2026, 4, 1 + match_id % 2),
        league="英超",
        home_team=f"H{match_id}",
        away_team=f"A{match_id}",
        bet_type="draw",
        odds=odds,
        is_hit=hit,
        total_score=108,
        handicap_value=0.25,
        had_d=odds,
        hhad_d=None,
        abs_hcap=0.25,
        rank_gap=5,
        recent_draw_sum=0.6,
        recent_low_scoring_sum=1.2,
        h2h_draw_rate=0.4,
        h2h_one_goal_margin_rate=0.4,
        home_recent_goal_diff=1,
        away_recent_goal_diff=-1,
    )


def test_random_baseline_is_reproducible():
    market = [_candidate(i, 3.0 + i * 0.01, i % 3 == 0) for i in range(1, 20)]
    a = run_random_combo_baseline(market, ticket_count=5, trials=20, seed=7)
    b = run_random_combo_baseline(market, ticket_count=5, trials=20, seed=7)
    assert a == b
    assert a["trials"] == 20
    assert "roi_p90" in a


def test_random_baseline_reports_model_percentile():
    market = [_candidate(i, 3.0, i % 2 == 0) for i in range(1, 20)]
    result = run_random_combo_baseline(market, ticket_count=4, trials=10, seed=1, model_roi=0.5)
    assert 0 <= result["model_roi_percentile"] <= 1
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_random_baseline.py -q
```

Expected: FAIL，提示 `No module named 'app.research.random_baseline'`。

- [ ] **Step 3: 实现随机对照**

创建 `backend/app/research/random_baseline.py`：

```python
from __future__ import annotations

import random

from app.research.combo import summarize_combo_tickets
from app.research.metrics import percentile_rank, quantile
from app.research.types import ComboTicket, ResearchCandidate


def _random_ticket_pair(rng: random.Random, candidates: list[ResearchCandidate], idx: int, *, stake: float) -> ComboTicket | None:
    if len(candidates) < 2:
        return None
    a, b = rng.sample(candidates, 2)
    combo_odds = round(a.odds * b.odds, 4)
    hit = a.is_hit and b.is_hit
    pnl = round((combo_odds - 1) * stake if hit else -stake, 4)
    return ComboTicket(
        strategy="same_day_strongest",
        ticket_date=min(a.match_date, b.match_date),
        legs=(a, b),
        combo_odds=combo_odds,
        is_hit=hit,
        pnl=pnl,
    )


def run_random_combo_baseline(
    market_candidates: list[ResearchCandidate],
    *,
    ticket_count: int,
    trials: int,
    seed: int,
    model_roi: float | None = None,
    stake: float = 100.0,
) -> dict:
    rng = random.Random(seed)
    rois: list[float] = []
    max_losing_streaks: list[int] = []
    for _ in range(trials):
        tickets = []
        for idx in range(ticket_count):
            ticket = _random_ticket_pair(rng, market_candidates, idx, stake=stake)
            if ticket is not None:
                tickets.append(ticket)
        summary = summarize_combo_tickets(tickets, total_days=max(1, ticket_count), stake=stake)
        rois.append(float(summary["roi"]))
        max_losing_streaks.append(int(summary["max_losing_streak"]))

    return {
        "trials": trials,
        "ticket_count": ticket_count,
        "roi_avg": sum(rois) / len(rois) if rois else 0.0,
        "roi_median": quantile(rois, 0.5),
        "roi_p80": quantile(rois, 0.8),
        "roi_p90": quantile(rois, 0.9),
        "roi_p95": quantile(rois, 0.95),
        "max_losing_streak_avg": sum(max_losing_streaks) / len(max_losing_streaks) if max_losing_streaks else 0.0,
        "model_roi_percentile": percentile_rank(model_roi, rois) if model_roi is not None else None,
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_random_baseline.py -q
```

Expected: `2 passed`。

---

## Task 6: DB 加载、报告输出和 CLI

**Files:**
- Create: `backend/app/research/repository.py`
- Create: `backend/app/research/reporting.py`
- Create: `backend/app/scripts/v33_research.py`
- Test: `backend/tests/test_research_reporting.py`

- [ ] **Step 1: 写报告输出测试**

创建 `backend/tests/test_research_reporting.py`：

```python
from pathlib import Path

from app.research.reporting import write_v33_report


def test_write_v33_report_creates_markdown_and_csv(tmp_path: Path):
    report_path = tmp_path / "report.md"
    bucket_path = tmp_path / "buckets.csv"
    combo_path = tmp_path / "combo.csv"
    random_path = tmp_path / "random.csv"

    write_v33_report(
        report_path=report_path,
        bucket_csv_path=bucket_path,
        combo_csv_path=combo_path,
        random_csv_path=random_path,
        summary={"model_name": "empirical-v32-filtered-candidate", "date_from": "2024-09-28", "date_to": "2026-04-22"},
        factor_buckets=[{"factor": "league", "label": "英超", "bets": 10, "hits": 4, "roi": 0.2}],
        combo_summaries=[{"strategy": "same_day_strongest", "combo_count": 5, "roi": 0.1}],
        random_summaries=[{"label": "全市场随机", "roi_avg": -0.1, "roi_p90": 0.05}],
    )

    assert "V3.3 单场因子诊断" in report_path.read_text(encoding="utf-8")
    assert bucket_path.read_text(encoding="utf-8").startswith("factor,label")
    assert combo_path.exists()
    assert random_path.exists()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_reporting.py -q
```

Expected: FAIL，提示 `No module named 'app.research.reporting'`。

- [ ] **Step 3: 实现 repository**

创建 `backend/app/research/repository.py`，负责：

```python
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.engine.service import _pick_odds
from app.models import League, ModelConfig, SportteryMatch, SportteryMatchScore
from app.research.types import ResearchCandidate
from app.scripts.v31_combination_candidate_backtest import enrich_features


def get_model_config_id(db: Session, model_name: str) -> int:
    cfg = db.query(ModelConfig).filter(ModelConfig.name == model_name).one()
    return cfg.id


def load_candidates(db: Session, *, model_config_id: int, start: date, end: date) -> list[ResearchCandidate]:
    rows = (
        db.query(SportteryMatchScore)
        .join(SportteryMatch, SportteryMatchScore.match_id == SportteryMatch.id)
        .join(League, SportteryMatch.league_id == League.id)
        .options(joinedload(SportteryMatchScore.match).joinedload(SportteryMatch.result))
        .options(joinedload(SportteryMatchScore.match).joinedload(SportteryMatch.team_stats))
        .options(joinedload(SportteryMatchScore.match).joinedload(SportteryMatch.odds))
        .filter(SportteryMatchScore.model_config_id == model_config_id)
        .filter(SportteryMatchScore.is_recommended.is_(True))
        .filter(SportteryMatch.match_date >= start)
        .filter(SportteryMatch.match_date <= end)
        .all()
    )
    candidates: list[ResearchCandidate] = []
    for score in rows:
        match = score.match
        if match.result is None or score.bet_type is None:
            continue
        odds = _pick_odds(match)
        if odds is None:
            continue
        price = float(odds.draw_odds if score.bet_type == "draw" else odds.draw_handicap_odds or 0)
        if price <= 0:
            continue
        raw = {
            "home_rank": getattr(match.team_stats, "home_rank", None),
            "away_rank": getattr(match.team_stats, "away_rank", None),
            "home_recent_form": getattr(match.team_stats, "home_recent_form", None),
            "away_recent_form": getattr(match.team_stats, "away_recent_form", None),
            "h2h_draws": getattr(match.team_stats, "h2h_draws", None),
            "h2h_home_wins": getattr(match.team_stats, "h2h_home_wins", None),
            "h2h_away_wins": getattr(match.team_stats, "h2h_away_wins", None),
            "h2h_matches_count": getattr(match.team_stats, "h2h_matches_count", None),
            "h2h_one_goal_margin_count": getattr(match.team_stats, "h2h_one_goal_margin_count", None),
            "home_recent_matches_count": getattr(match.team_stats, "home_recent_matches_count", None),
            "away_recent_matches_count": getattr(match.team_stats, "away_recent_matches_count", None),
            "home_recent_low_scoring_count": getattr(match.team_stats, "home_recent_low_scoring_count", None),
            "away_recent_low_scoring_count": getattr(match.team_stats, "away_recent_low_scoring_count", None),
            "home_recent_goal_diff": getattr(match.team_stats, "home_recent_goal_diff", None),
            "away_recent_goal_diff": getattr(match.team_stats, "away_recent_goal_diff", None),
            "abs_hcap": abs(float(odds.handicap_value)) if odds.handicap_value is not None else None,
        }
        features = enrich_features(raw)
        candidates.append(
            ResearchCandidate(
                match_id=match.id,
                match_date=match.match_date.date(),
                league=match.league.name,
                home_team=match.home_team,
                away_team=match.away_team,
                bet_type=score.bet_type,
                odds=price,
                is_hit=(match.result.result == "draw") if score.bet_type == "draw" else (match.result.handicap_result == "draw"),
                total_score=score.total_score,
                handicap_value=float(odds.handicap_value) if odds.handicap_value is not None else None,
                had_d=float(odds.draw_odds) if odds.draw_odds is not None else None,
                hhad_d=float(odds.draw_handicap_odds) if odds.draw_handicap_odds is not None else None,
                abs_hcap=features.get("abs_hcap"),
                rank_gap=features.get("rank_gap"),
                recent_draw_sum=features.get("recent_draw_sum"),
                recent_low_scoring_sum=features.get("recent_low_scoring_sum"),
                h2h_draw_rate=features.get("h2h_draw_rate"),
                h2h_one_goal_margin_rate=features.get("h2h_one_goal_margin_rate"),
                home_recent_goal_diff=features.get("home_recent_goal_diff"),
                away_recent_goal_diff=features.get("away_recent_goal_diff"),
            )
        )
    return candidates
```

- [ ] **Step 4: 实现 reporting**

创建 `backend/app/research/reporting.py`，实现 `write_v33_report(...)`，写 Markdown 和三个 CSV。CSV 字段使用传入字典 keys 的并集。

- [ ] **Step 5: 实现 CLI**

创建 `backend/app/scripts/v33_research.py`，参数：

```text
--start YYYY-MM-DD
--end YYYY-MM-DD
--model empirical-v32-filtered-candidate
--random-trials 1000
--random-seed 20260426
--report docs/analysis/2026-04-26-v33-single-factor-and-combo-diagnostic.md
--replace
```

CLI 流程：

1. 加载 V3.2 候选。
2. 生成 factor buckets。
3. 生成三种组合策略摘要。
4. 生成随机组摘要。
5. 写 Markdown 和 CSV。
6. 写入 `model_research_runs` 和 `model_research_artifacts`。

- [ ] **Step 6: 跑报告测试**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_reporting.py -q
```

Expected: `1 passed`。

---

## Task 7: 研究 API 和页面摘要

**Files:**
- Create: `backend/app/schemas/research.py`
- Create: `backend/app/api/research.py`
- Modify: `backend/app/main.py`
- Create: `frontend/lib/research/types.ts`
- Create: `frontend/lib/research/api.ts`
- Create: `frontend/app/backtest/research-summary.tsx`
- Modify: `frontend/app/backtest/backtest-client.tsx`
- Test: `frontend/tests/research-api.test.ts`
- Test: `frontend/tests/research-summary.test.tsx`

- [ ] **Step 1: 后端 API**

新增 `/api/research/latest`，返回最新 succeeded run：

```json
{
  "id": 1,
  "name": "v33-single-factor-combo-diagnostic",
  "base_model_config_id": 8,
  "date_from": "2024-09-28",
  "date_to": "2026-04-22",
  "status": "succeeded",
  "summary_json": {},
  "report_path": "docs/analysis/2026-04-26-v33-single-factor-and-combo-diagnostic.md",
  "created_at": "2026-04-26T14:30:00"
}
```

- [ ] **Step 2: 前端 API 测试和实现**

`frontend/lib/research/api.ts` 调用：

```ts
import { apiFetch } from '@/lib/auth/api'
import type { ResearchRun } from './types'

export async function getLatestResearchRun(): Promise<ResearchRun | null> {
  return apiFetch<ResearchRun | null>('/api/research/latest')
}
```

- [ ] **Step 3: 页面组件**

`ResearchSummary` 展示：

1. 研究名称。
2. 数据范围。
3. 模型 ROI vs 随机 ROI。
4. 覆盖率。
5. 报告路径。

无数据时展示“暂无研究报告”。

- [ ] **Step 4: 前端测试**

Run:

```bash
cd frontend && pnpm test -- research-api.test.ts research-summary.test.tsx
```

Expected: 相关测试通过。

---

## Task 8: 生成 V3.3 报告和验证

**Files:**
- Modify: `docs/analysis/MODEL_RESEARCH_INDEX.md`
- Generate: `docs/analysis/2026-04-26-v33-single-factor-and-combo-diagnostic.md`
- Generate: `docs/analysis/v33-single-factor-buckets.csv`
- Generate: `docs/analysis/v33-combo-simulation.csv`
- Generate: `docs/analysis/v33-random-baseline.csv`

- [ ] **Step 1: 运行数据库迁移**

Run:

```bash
cd backend && MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308 MYSQL_DATABASE=sporttery_10x MYSQL_USER=sporttery MYSQL_PASSWORD=sporttery_pass .venv/bin/alembic upgrade head
```

Expected: `0012` 已应用。

- [ ] **Step 2: 运行 V3.3 研究脚本**

Run:

```bash
MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308 MYSQL_DATABASE=sporttery_10x MYSQL_USER=sporttery MYSQL_PASSWORD=sporttery_pass PYTHONPATH=backend backend/.venv/bin/python -m app.scripts.v33_research --start 2024-09-28 --end 2026-04-22 --model empirical-v32-filtered-candidate --random-trials 1000 --random-seed 20260426 --replace --report docs/analysis/2026-04-26-v33-single-factor-and-combo-diagnostic.md
```

Expected:

```text
run_id=<id> candidates=561 factor_buckets=<n> combo_summaries=3 random_baselines=2
```

- [ ] **Step 3: 更新模型研究索引**

将 `docs/analysis/MODEL_RESEARCH_INDEX.md` 的 V3.3 行改为“已生成”，补充报告路径和 run id。

- [ ] **Step 4: 后端全量相关测试**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_metrics.py tests/test_research_factors.py tests/test_research_combo.py tests/test_research_random_baseline.py tests/test_research_reporting.py tests/test_v31_combination_candidate_backtest.py tests/test_incremental_signal_validation.py -q
```

Expected: 全部通过。

- [ ] **Step 5: Ruff**

Run:

```bash
cd backend && .venv/bin/python -m ruff check app/research app/scripts/v33_research.py app/api/research.py app/schemas/research.py tests/test_research_metrics.py tests/test_research_factors.py tests/test_research_combo.py tests/test_research_random_baseline.py tests/test_research_reporting.py
```

Expected: `All checks passed!`

- [ ] **Step 6: 浏览器验证**

在 `http://localhost:3000/backtest`：

1. 页面出现研究报告摘要。
2. 摘要显示 V3.3 名称、数据范围、模型 vs 随机对照。
3. 历史回测列表仍显示 V3.2 回测 #98-#105。
4. 今日推荐不受影响。

---

## Spec Coverage 自检

| 设计要求 | 覆盖任务 |
| --- | --- |
| 单场因子诊断 | Task 3, Task 6 |
| 二串一同日/两日/高赔策略 | Task 4, Task 6 |
| 随机对照组 | Task 5, Task 6 |
| 结构化研究表 | Task 1, Task 6 |
| 页面展示入口 | Task 7, Task 8 |
| 文档新鲜度 | Task 8 |
| 不影响 active 模型/今日推荐 | Task 6-8 验证 |
| 代码分层 | Task 2-7 文件结构 |

## Placeholder 自检

本计划没有未完成占位词；每个实现任务都有明确文件、命令和期望结果。

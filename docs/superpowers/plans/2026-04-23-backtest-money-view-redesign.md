# Backtest 彩民视角改造 · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `/backtest` 页面改造成「彩民钱袋子」视角：表单可设置每场固定投注金额；页面显示固定/Kelly 两套真实金额概览 + 每场下注明细 + 专业术语 Tooltip；后端持久化 `fixed_stake` 和 `bets_detail` JSON 快照。

**Architecture:** 后端先扩展数据模型（migration → model → schema）和业务逻辑（`simulate_bet` 支持真实金额 + `BacktestService` 构造 `bets_detail`），再同步前端类型，最后用 Shadcn 风格的 Tooltip + 新明细表重写 UI。后端改动可独立合并；前端改动依赖后端新字段。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 / Pydantic v2 / Alembic / MySQL 8；TypeScript / Next.js App Router / React 18 / Radix UI Tooltip / recharts。

关联 Spec：`docs/superpowers/specs/2026-04-23-backtest-money-view-redesign.md`。

---

## 文件结构

**后端新建**：
- `backend/alembic/versions/0010_backtest_stake_and_details.py`
- `backend/tests/test_backtest_money.py`

**后端修改**：
- `backend/app/models/backtest.py` — 增加 `fixed_stake` / `bets_detail` 列
- `backend/app/schemas/backtest.py` — `BacktestCreate` / `BacktestSummary` 新字段
- `backend/app/engine/backtest.py` — `simulate_bet` 支持 `stake_fixed` 参数
- `backend/app/engine/backtest_service.py` — `run` 接收 `fixed_stake`，构造 `bets_detail`
- `backend/app/api/backtest.py` — 转发 `fixed_stake`

**前端新建**：
- `frontend/components/info-tooltip/info-tooltip.tsx`
- `frontend/components/info-tooltip/info-tooltip.module.css`
- `frontend/lib/backtest/tooltips.ts`
- `frontend/app/backtest/backtest-bets-table.tsx`
- `frontend/app/backtest/backtest-bets-table.module.css`

**前端修改**：
- `frontend/lib/backtest/types.ts` — 增加 `BetDetail` 类型和 `fixed_stake` / `bets_detail`
- `frontend/app/backtest/backtest-form.tsx` — 增加「每场固定投注金额」字段 + tooltip
- `frontend/app/backtest/backtest-summary.tsx` — 6 卡 + 辅助信息横幅
- `frontend/app/backtest/backtest-client.tsx` — 在概览下方挂载 `BacktestBetsTable`
- `frontend/app/backtest/backtest-client.module.css` — 新增 `summaryBanner`、卡片 `cardPositive` / `cardNegative` 颜色

---

## Task 序列

### Task 1: Alembic Migration 添加 backtest_sessions 新列

**Files:**
- Create: `backend/alembic/versions/0010_backtest_stake_and_details.py`

- [ ] **Step 1: 写 migration 文件**

```python
"""add fixed_stake & bets_detail to backtest_sessions

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-23 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "backtest_sessions",
        sa.Column(
            "fixed_stake",
            sa.DECIMAL(14, 2),
            nullable=True,
            comment="每场固定投注金额(CNY)",
        ),
    )
    op.add_column(
        "backtest_sessions",
        sa.Column(
            "bets_detail",
            sa.JSON(),
            nullable=True,
            comment="每场下注明细 JSON 快照",
        ),
    )


def downgrade() -> None:
    op.drop_column("backtest_sessions", "bets_detail")
    op.drop_column("backtest_sessions", "fixed_stake")
```

- [ ] **Step 2: 应用 migration**

```bash
cd backend && docker compose -f ../docker-compose.yml exec backend alembic upgrade head
```

预期输出：`Running upgrade 0009 -> 0010, add fixed_stake & bets_detail to backtest_sessions`

- [ ] **Step 3: 用 MySQL 客户端验证**

```bash
docker compose exec mysql mysql -usporttery -psporttery sporttery_10x -e "DESCRIBE backtest_sessions" | grep -E 'fixed_stake|bets_detail'
```

预期：看到两行分别是 `fixed_stake decimal(14,2) YES` 和 `bets_detail json YES`。

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/0010_backtest_stake_and_details.py
git commit -m "feat(db): add fixed_stake & bets_detail to backtest_sessions"
```

---

### Task 2: 扩展 BacktestSession ORM

**Files:**
- Modify: `backend/app/models/backtest.py`

- [ ] **Step 1: 在 `BacktestSession` 类尾部（`kelly_roi` 之后、relationships 之前）加入两列**

```python
    fixed_stake: Mapped[Decimal | None] = mapped_column(
        DECIMAL(14, 2), nullable=True, comment="每场固定投注金额(CNY)",
    )
    bets_detail: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True, comment="每场下注明细 JSON 快照",
    )
```

- [ ] **Step 2: 打开 Python shell 验证模型可实例化**

```bash
cd backend && .venv/bin/python -c "from app.models import BacktestSession; print(BacktestSession.__table__.columns['fixed_stake'].type, BacktestSession.__table__.columns['bets_detail'].type)"
```

预期输出：`DECIMAL(14, 2) JSON`

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/backtest.py
git commit -m "feat(model): BacktestSession 新增 fixed_stake/bets_detail"
```

---

### Task 3: 扩展 Pydantic Schemas

**Files:**
- Modify: `backend/app/schemas/backtest.py`

- [ ] **Step 1: 在 `BacktestCreate` 加入 `fixed_stake`**

把 `BacktestCreate` 类改为：

```python
class BacktestCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_config_id: int | None = None
    date_from: date
    date_to: date
    mode: BacktestMode = "both"
    initial_capital: Decimal = Field(default=Decimal("10000"), ge=0)
    fixed_stake: Decimal = Field(default=Decimal("100"), ge=Decimal("0.01"))
```

- [ ] **Step 2: 在 `BacktestSummary` 加入两个可空字段**

在 `initial_capital: Decimal | None = None` 那一行下面紧接着加：

```python
    fixed_stake: Decimal | None = None
    bets_detail: list[dict[str, Any]] | None = None
```

- [ ] **Step 3: 快速验证**

```bash
cd backend && .venv/bin/python -c "from app.schemas.backtest import BacktestCreate, BacktestSummary; print(BacktestCreate().fixed_stake)" 2>&1 | head -20
```

预期：`100` 或报 `date_from` 缺失（缺字段的 ValidationError 是正常的，重点是 import 不报错）。

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/backtest.py
git commit -m "feat(schema): Backtest{Create,Summary} 支持 fixed_stake/bets_detail"
```

---

### Task 4: `simulate_bet` 支持真实 fixed stake 金额

当前 `simulate_bet` 中 `pnl_fixed = odds - 1` 或 `-1`（等于 1 单位），需要改成 `stake_fixed × (odds - 1)` 或 `-stake_fixed`。新增可选参数 `stake_fixed: Decimal = Decimal("1")`，保留向后兼容。

**Files:**
- Modify: `backend/app/engine/backtest.py`
- Test: `backend/tests/test_backtest_money.py`

- [ ] **Step 1: 写失败的测试**

新建 `backend/tests/test_backtest_money.py`：

```python
from decimal import Decimal

from app.engine.backtest import simulate_bet


def test_simulate_bet_fixed_stake_hit():
    pnl_fixed, pnl_kelly, stake_kelly = simulate_bet(
        odds=Decimal("3.10"),
        kelly_pct=Decimal("0"),
        current_capital=Decimal("0"),
        is_hit=True,
        stake_fixed=Decimal("100"),
    )
    assert pnl_fixed == Decimal("210.00")
    assert pnl_kelly == Decimal("0.00")
    assert stake_kelly == Decimal("0.00")


def test_simulate_bet_fixed_stake_miss():
    pnl_fixed, _, _ = simulate_bet(
        odds=Decimal("3.10"),
        kelly_pct=Decimal("0"),
        current_capital=Decimal("0"),
        is_hit=False,
        stake_fixed=Decimal("100"),
    )
    assert pnl_fixed == Decimal("-100.00")


def test_simulate_bet_fixed_stake_default_unit():
    """Backwards-compatible: stake_fixed defaults to 1."""
    pnl_fixed, _, _ = simulate_bet(
        odds=Decimal("3.10"),
        kelly_pct=Decimal("0"),
        current_capital=Decimal("0"),
        is_hit=True,
    )
    assert pnl_fixed == Decimal("2.10")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && .venv/bin/python -m pytest tests/test_backtest_money.py::test_simulate_bet_fixed_stake_hit -v
```

预期：FAIL（`simulate_bet` 不接受 `stake_fixed` 参数）。

- [ ] **Step 3: 实现改动**

把 `backend/app/engine/backtest.py` 的 `simulate_bet` 签名和函数体改为：

```python
def simulate_bet(
    *,
    odds: Decimal,
    kelly_pct: Decimal,
    current_capital: Decimal,
    is_hit: bool,
    stake_fixed: Decimal = Decimal("1"),
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute (pnl_fixed, pnl_kelly, stake_kelly) for a single bet.

    ``stake_fixed`` is the real amount wagered per bet under the fixed-stake
    mode; defaults to 1 so callers that want unit accounting still work.

    Bankruptcy guard: when current_capital <= 0 the Kelly simulation is
    halted (stake_kelly = 0, pnl_kelly = 0). The fixed-stake accounting still
    applies, because it operates on ``stake_fixed`` decoupled from rolling
    capital.
    """
    if current_capital <= Decimal("0") or kelly_pct <= Decimal("0"):
        stake_kelly = Decimal("0.00")
        pnl_kelly = Decimal("0.00")
    else:
        stake_kelly = (current_capital * kelly_pct).quantize(Decimal("0.01"))
        pnl_kelly = (
            (stake_kelly * (odds - Decimal("1"))).quantize(Decimal("0.01"))
            if is_hit
            else (-stake_kelly).quantize(Decimal("0.01"))
        )
    pnl_fixed = (
        (stake_fixed * (odds - Decimal("1"))).quantize(Decimal("0.01"))
        if is_hit
        else (-stake_fixed).quantize(Decimal("0.01"))
    )
    return pnl_fixed, pnl_kelly, stake_kelly
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && .venv/bin/python -m pytest tests/test_backtest_money.py -v
```

预期：3 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/backtest.py backend/tests/test_backtest_money.py
git commit -m "feat(engine): simulate_bet 支持 stake_fixed 金额参数"
```

---

### Task 5: `BacktestService.run` 使用 fixed_stake & 构造 bets_detail

**Files:**
- Modify: `backend/app/engine/backtest_service.py`
- Test: `backend/tests/test_backtest_money.py`

- [ ] **Step 1: 写失败的测试（在同一文件追加）**

在 `backend/tests/test_backtest_money.py` 末尾追加：

```python
from datetime import date, datetime, time

import pytest
from app.engine.backtest_service import BacktestService
from app.models import (
    BacktestSession,
    League,
    ModelConfig,
    SportteryMatch,
    SportteryMatchOdds,
    SportteryMatchResult,
    SportteryMatchTeamStats,
)
from app.scripts.seed import DEFAULT_KELLY_BANDS, DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS
from sqlalchemy.orm import Session


@pytest.fixture
def config(db: Session) -> ModelConfig:
    cfg = ModelConfig(
        name="default",
        weights_json=dict(DEFAULT_WEIGHTS),
        thresholds_json=dict(DEFAULT_THRESHOLDS),
        kelly_bands_json=dict(DEFAULT_KELLY_BANDS),
    )
    db.add(cfg)
    db.flush()
    return cfg


@pytest.fixture
def league(db: Session) -> League:
    lg = League(name="英超")
    db.add(lg)
    db.flush()
    return lg


def _make_draw_match(db: Session, league: League, match_date: date) -> SportteryMatch:
    m = SportteryMatch(
        logical_id=int(match_date.strftime("%Y%m%d") + "6001"),
        league_id=league.id,
        home_team="H",
        away_team="A",
        match_date=datetime.combine(match_date, time(20, 0)),
        status="finished",
    )
    db.add(m)
    db.flush()

    db.add(
        SportteryMatchOdds(
            match_id=m.id,
            source="sporttery",
            win_odds=Decimal("2.50"),
            draw_odds=Decimal("3.10"),
            lose_odds=Decimal("2.60"),
            handicap_value=Decimal("0.0"),
            draw_handicap_odds=Decimal("3.60"),
            asian_handicap="0.00",
            total_goals=Decimal("2.25"),
            scraped_at=datetime(2026, 4, 1, 12, 0),
        )
    )
    db.add(
        SportteryMatchTeamStats(
            match_id=m.id,
            home_rank=5,
            away_rank=6,
            home_season_wins=10,
            home_season_draws=8,
            home_season_losses=6,
            away_season_wins=9,
            away_season_draws=9,
            away_season_losses=7,
            home_recent_form="WDDLW",
            away_recent_form="DDWLL",
            scraped_at=datetime(2026, 4, 1, 12, 0),
        )
    )
    db.add(
        SportteryMatchResult(
            match_id=m.id,
            home_score=1,
            away_score=1,
            result="draw",
            handicap_result="draw",
        )
    )
    return m


def test_backtest_run_uses_fixed_stake(db: Session, config: ModelConfig, league: League):
    _make_draw_match(db, league, date(2026, 4, 1))
    db.commit()

    svc = BacktestService(db)
    session = svc.run(
        model_config_id=config.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 2),
        fixed_stake=Decimal("50"),
    )
    assert session.fixed_stake == Decimal("50.00")
    if session.total_bets > 0:
        assert session.profit_loss == Decimal("50") * (Decimal("3.10") - Decimal("1"))


def test_backtest_run_populates_bets_detail(
    db: Session, config: ModelConfig, league: League
):
    _make_draw_match(db, league, date(2026, 4, 1))
    db.commit()

    svc = BacktestService(db)
    session = svc.run(
        model_config_id=config.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 2),
        fixed_stake=Decimal("100"),
    )
    assert session.bets_detail is not None
    assert isinstance(session.bets_detail, list)
    assert len(session.bets_detail) == session.total_bets
    if session.total_bets > 0:
        row = session.bets_detail[0]
        assert row["match_id"]
        assert row["match_date"] == "2026-04-01"
        assert row["league"] == "英超"
        assert row["bet_type"] in ("draw", "handicap_draw")
        assert row["stake_fixed"] == "100.00"
        assert row["is_hit"] is True
        assert row["home_score"] == 1
        assert row["away_score"] == 1
        assert row["pnl_fixed"] == "210.00"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && .venv/bin/python -m pytest tests/test_backtest_money.py::test_backtest_run_uses_fixed_stake -v
```

预期：FAIL（`run` 不接受 `fixed_stake`）。

- [ ] **Step 3: 修改 `BacktestService.run` 签名并构造明细**

在 `backend/app/engine/backtest_service.py` 里：

3.1 把 `run` 方法签名改为：

```python
    def run(
        self,
        *,
        model_config_id: int,
        date_from: date,
        date_to: date,
        mode: str = "both",
        initial_capital: Decimal = Decimal("10000"),
        fixed_stake: Decimal = Decimal("100"),
        user_id: int | None = None,
    ) -> BacktestSession:
```

3.2 在 `outcomes: list[BetOutcome] = []` 下面追加：

```python
        bets_detail: list[dict] = []
```

3.3 把循环里的 `simulate_bet(...)` 调用改为传入 `stake_fixed=Decimal(fixed_stake)`：

```python
            pnl_fixed, pnl_kelly, stake_kelly = simulate_bet(
                odds=Decimal(bet_odds),
                kelly_pct=kelly_pct_val,
                current_capital=capital,
                is_hit=is_hit,
                stake_fixed=Decimal(fixed_stake),
            )
```

3.4 把 `outcomes.append(BetOutcome(...))` 的 `stake_fixed=Decimal("1")` 改为 `stake_fixed=Decimal(fixed_stake)`：

```python
                    stake_fixed=Decimal(fixed_stake),
```

3.5 紧接在 `outcomes.append(...)` 后（仍在 for 循环内）追加构造明细的代码：

```python
            bets_detail.append(
                {
                    "match_id": match.id,
                    "match_date": match.match_date.date().isoformat(),
                    "league": match.league.name if match.league else "",
                    "home_team": match.home_team,
                    "away_team": match.away_team,
                    "bet_type": score.bet_type,
                    "total_score": int(score.total_score),
                    "odds": str(Decimal(bet_odds).quantize(Decimal("0.01"))),
                    "stake_fixed": str(Decimal(fixed_stake).quantize(Decimal("0.01"))),
                    "stake_kelly": str(stake_kelly),
                    "is_hit": is_hit,
                    "home_score": result.home_score,
                    "away_score": result.away_score,
                    "pnl_fixed": str(pnl_fixed),
                    "pnl_kelly": str(pnl_kelly),
                }
            )
```

3.6 把最后的 `return self._persist(...)` 调用传入新参数：

```python
        return self._persist(
            model_config_id=model_config_id,
            date_from=date_from,
            date_to=date_to,
            mode=mode,
            initial_capital=Decimal(initial_capital),
            fixed_stake=Decimal(fixed_stake),
            bets_detail=bets_detail,
            stats=stats,
            user_id=user_id,
        )
```

3.7 把 `_persist` 方法签名扩展：

```python
    def _persist(
        self,
        *,
        model_config_id: int,
        date_from: date,
        date_to: date,
        mode: str,
        initial_capital: Decimal,
        fixed_stake: Decimal,
        bets_detail: list[dict],
        stats,
        user_id: int | None = None,
    ) -> BacktestSession:
```

3.8 在 `_persist` 内构造 `BacktestSession(...)` 时，把 `profit_loss` 改为用真实金额合计，并新增两个字段：

```python
        session = BacktestSession(
            user_id=user_id,
            model_config_id=model_config_id,
            date_from=date_from,
            date_to=date_to,
            total_bets=stats.total_bets,
            hit_count=stats.hit_count,
            hit_rate=Decimal(stats.hit_rate).quantize(Decimal("0.0001")),
            roi=Decimal(stats.roi_fixed).quantize(Decimal("0.0001")),
            profit_loss=Decimal(stats.profit_loss_fixed).quantize(Decimal("0.01")),
            kelly_profit_loss=Decimal(stats.profit_loss_kelly).quantize(
                Decimal("0.01")
            ),
            kelly_roi=Decimal(stats.roi_kelly).quantize(Decimal("0.0001")),
            mode=mode,
            initial_capital=initial_capital,
            fixed_stake=fixed_stake,
            bets_detail=bets_detail or None,
            results_by_score=_decimalize(stats.by_score_band),
            results_by_league=_decimalize(stats.by_league),
            equity_curve=_decimalize(stats.equity_curve),
        )
```

> 说明：`stats.profit_loss_fixed` 和 `stats.roi_fixed` 会自动反映真实金额，因为 `simulate_bet` 现在按 `stake_fixed` 计算 PnL；`aggregate` 里的求和逻辑用同一个 `o.stake_fixed`。

- [ ] **Step 4: 运行所有 backtest 测试**

```bash
cd backend && .venv/bin/python -m pytest tests/test_backtest_money.py tests/test_backtest_api.py -v
```

预期：money 测试全部通过；`test_backtest_api.py` 因不同场景可能跳过，但不新增失败。

> 注意：`tests/test_backtest_service.py` 使用旧 `Match` 名字（pre-existing import error），运行时用 `--ignore=tests/test_backtest_service.py` 跳过。

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/backtest_service.py backend/tests/test_backtest_money.py
git commit -m "feat(engine): BacktestService 支持 fixed_stake & bets_detail"
```

---

### Task 6: API 层透传 fixed_stake

**Files:**
- Modify: `backend/app/api/backtest.py`

- [ ] **Step 1: 修改 `create_backtest`**

把 `svc.run(...)` 调用改为：

```python
    session = svc.run(
        model_config_id=cfg_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
        mode=payload.mode,
        initial_capital=payload.initial_capital,
        fixed_stake=payload.fixed_stake,
        user_id=user.id,
    )
```

- [ ] **Step 2: 运行 API 测试**

```bash
cd backend && .venv/bin/python -m pytest tests/test_backtest_api.py -v
```

预期：原有 API 测试仍通过（`fixed_stake` 未传时用默认 100）。

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/backtest.py
git commit -m "feat(api): POST /api/backtest 支持 fixed_stake 参数"
```

---

### Task 7: 前端 types 同步

**Files:**
- Modify: `frontend/lib/backtest/types.ts`

- [ ] **Step 1: 在现有 types 文件追加新类型并扩展接口**

打开 `frontend/lib/backtest/types.ts`，找到 `BacktestSummary` 接口，在 `initial_capital: string | number | null` 行下面追加：

```ts
  fixed_stake: string | number | null
  bets_detail: BetDetail[] | null
```

在文件顶部、`export interface EquityCurvePoint` 之前追加：

```ts
export interface BetDetail {
  match_id: number
  match_date: string
  league: string
  home_team: string
  away_team: string
  bet_type: 'draw' | 'handicap_draw'
  total_score: number
  odds: string
  stake_fixed: string
  stake_kelly: string
  is_hit: boolean
  home_score: number
  away_score: number
  pnl_fixed: string
  pnl_kelly: string
}
```

把 `BacktestCreatePayload` 接口改为：

```ts
export interface BacktestCreatePayload {
  model_config_id?: number | null
  date_from: string
  date_to: string
  mode?: BacktestMode
  initial_capital?: number
  fixed_stake?: number
}
```

- [ ] **Step 2: 让 TypeScript 检查通过**

```bash
cd frontend && npm run typecheck
```

预期：无错误。若脚本不存在，改用 `npx tsc --noEmit`。

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/backtest/types.ts
git commit -m "feat(fe): backtest types 增加 BetDetail & fixed_stake"
```

---

### Task 8: 通用 InfoTooltip 组件

**Files:**
- Create: `frontend/components/info-tooltip/info-tooltip.tsx`
- Create: `frontend/components/info-tooltip/info-tooltip.module.css`

- [ ] **Step 1: 确认 Radix Tooltip 已安装**

```bash
cd frontend && grep -E '"@radix-ui/react-tooltip"' package.json
```

如果无输出，执行：

```bash
cd frontend && npm install @radix-ui/react-tooltip
```

- [ ] **Step 2: 写组件**

`frontend/components/info-tooltip/info-tooltip.tsx`：

```tsx
'use client'

import * as Tooltip from '@radix-ui/react-tooltip'
import styles from './info-tooltip.module.css'

interface InfoTooltipProps {
  text: string
  label?: string
}

export function InfoTooltip ({ text, label = '?' }: InfoTooltipProps) {
  return (
    <Tooltip.Provider delayDuration={150}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button type="button" className={styles.trigger} aria-label={text}>
            {label}
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content className={styles.content} sideOffset={4}>
            {text}
            <Tooltip.Arrow className={styles.arrow} />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}
```

`frontend/components/info-tooltip/info-tooltip.module.css`：

```css
.trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 9999px;
  background: rgb(51 65 85);
  color: rgb(203 213 225);
  font-size: 10px;
  font-weight: 600;
  margin-left: 4px;
  border: 0;
  cursor: help;
  padding: 0;
}

.trigger:hover {
  background: rgb(71 85 105);
}

.content {
  background: rgb(15 23 42);
  color: rgb(226 232 240);
  font-size: 12px;
  line-height: 1.4;
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid rgb(51 65 85);
  max-width: 260px;
  z-index: 100;
}

.arrow {
  fill: rgb(15 23 42);
}
```

- [ ] **Step 3: TypeScript 检查**

```bash
cd frontend && npx tsc --noEmit
```

预期：无错。

- [ ] **Step 4: Commit**

```bash
git add frontend/components/info-tooltip/
git commit -m "feat(fe): 新增 InfoTooltip 通用组件"
```

---

### Task 9: Tooltip 文案常量

**Files:**
- Create: `frontend/lib/backtest/tooltips.ts`

- [ ] **Step 1: 写文件**

```ts
export const TOOLTIPS = {
  mode: '两者兼顾：同时计算固定和 Kelly 两种策略，便于对比。',
  fixed_stake: '固定模式下每场下注的金额（元）。不管评分高低都下这个数，便于简单评估。',
  initial_capital: 'Kelly 模式下的总资金池，凯利公式按当前本金比例决定每场下注金额。',
  model_config_id: '使用哪套模型规则。留空则用当前激活的模型。',
  bet_type: '模型建议下注的玩法：平局 = 直接买平；让球平 = 买让球后的平局。',
  total_score: '模型 6 维评分合计，满分 120。≥ 84 才会被推荐。',
  odds: '下注玩法对应的真实赔率（澳门欧赔）。下注金额 × 赔率 = 命中时的奖金。',
  stake_kelly: '凯利公式按评分高低自动分配的下注金额。评分越高投注越多。',
  roi_fixed: '固定模式总回报率：净盈亏 ÷ 总投入。',
  roi_kelly: 'Kelly 模式总回报率：净盈亏 ÷ 初始本金。'
} as const

export const BET_TYPE_LABEL: Record<string, string> = {
  draw: '平局',
  handicap_draw: '让球平'
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/backtest/tooltips.ts
git commit -m "feat(fe): 新增 backtest tooltip 文案常量"
```

---

### Task 10: 表单新增「每场固定投注金额」字段

**Files:**
- Modify: `frontend/app/backtest/backtest-form.tsx`

- [ ] **Step 1: 增加 state 和字段**

1.1 在 `useState` 声明区域追加：

```tsx
  const [fixedStake, setFixedStake] = useState('100')
```

1.2 替换 `handleSubmit` 里的 `payload` 为：

```tsx
    const payload: BacktestCreatePayload = {
      date_from: dateFrom,
      date_to: dateTo,
      mode,
      initial_capital: Number(initialCapital) || 10000,
      fixed_stake: Number(fixedStake) || 100
    }
    if (modelConfigId) payload.model_config_id = Number(modelConfigId)
    await onSubmit(payload)
```

1.3 import 两个新东西（文件顶部）：

```tsx
import { InfoTooltip } from '@/components/info-tooltip/info-tooltip'
import { TOOLTIPS } from '@/lib/backtest/tooltips'
```

1.4 在 `<label>资金模式</label>` 和 `<label>初始本金</label>` 之间插入新字段，并给所有带术语的 label 加上 tooltip。完整 JSX 替换为：

```tsx
  return (
    <form className={styles.form} onSubmit={handleSubmit} aria-label="backtest-form">
      <label className={styles.formField}>
        起始日期
        <input
          className={styles.input}
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          required
        />
      </label>
      <label className={styles.formField}>
        结束日期
        <input
          className={styles.input}
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          required
        />
      </label>
      <label className={styles.formField}>
        <span>
          资金模式
          <InfoTooltip text={TOOLTIPS.mode} />
        </span>
        <select
          className={styles.select}
          value={mode}
          onChange={(e) => setMode(e.target.value as BacktestMode)}
        >
          <option value="both">两者兼顾</option>
          <option value="fixed">固定单位</option>
          <option value="kelly">Kelly</option>
        </select>
      </label>
      <label className={styles.formField}>
        <span>
          每场固定投注金额（元）
          <InfoTooltip text={TOOLTIPS.fixed_stake} />
        </span>
        <input
          className={styles.input}
          type="number"
          min="1"
          step="10"
          value={fixedStake}
          onChange={(e) => setFixedStake(e.target.value)}
        />
      </label>
      <label className={styles.formField}>
        <span>
          初始本金（元）
          <InfoTooltip text={TOOLTIPS.initial_capital} />
        </span>
        <input
          className={styles.input}
          type="number"
          min="0"
          step="100"
          value={initialCapital}
          onChange={(e) => setInitialCapital(e.target.value)}
        />
      </label>
      <label className={styles.formField}>
        <span>
          模型配置 ID（可空）
          <InfoTooltip text={TOOLTIPS.model_config_id} />
        </span>
        <input
          className={styles.input}
          type="number"
          min="1"
          value={modelConfigId}
          onChange={(e) => setModelConfigId(e.target.value)}
          placeholder="默认使用第一条"
        />
      </label>
      <div className={styles.actions}>
        <button className={styles.buttonPrimary} type="submit" disabled={loading}>
          {loading ? '回测中…' : '开始回测'}
        </button>
      </div>
    </form>
  )
```

- [ ] **Step 2: TypeScript 检查**

```bash
cd frontend && npx tsc --noEmit
```

预期：无错。

- [ ] **Step 3: Commit**

```bash
git add frontend/app/backtest/backtest-form.tsx
git commit -m "feat(fe): backtest 表单增加 fixed_stake 字段"
```

---

### Task 11: 概览区扩展为 6 卡 + 辅助信息横幅

**Files:**
- Modify: `frontend/app/backtest/backtest-summary.tsx`
- Modify: `frontend/app/backtest/backtest-client.module.css`

- [ ] **Step 1: 新增 CSS 样式**

在 `frontend/app/backtest/backtest-client.module.css` 末尾追加：

```css
.summaryBanner {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.5rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
  color: rgb(148 163 184);
}

.cardPositive .cardValue {
  color: rgb(74 222 128);
}

.cardNegative .cardValue {
  color: rgb(248 113 113);
}

.cardSection {
  font-size: 0.75rem;
  color: rgb(148 163 184);
  margin-bottom: 0.25rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
```

- [ ] **Step 2: 重写 BacktestSummary**

把 `frontend/app/backtest/backtest-summary.tsx` 的整体结构改为两行卡片 + 辅助横幅。保留曲线图和饼图。完整替换文件内容为：

```tsx
'use client'

import {
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts'

import type { BacktestSummary as BacktestSummaryData } from '@/lib/backtest/types'

import styles from './backtest-client.module.css'

const BAND_COLORS = ['#22d3ee', '#34d399', '#f97316', '#a78bfa', '#f43f5e', '#f59e0b']

interface BacktestSummaryProps {
  data: BacktestSummaryData
}

function toNum (v: string | number | null | undefined): number {
  if (v === null || v === undefined) return 0
  return typeof v === 'string' ? parseFloat(v) : v
}

function pct (v: string | number | null | undefined): string {
  return `${(toNum(v) * 100).toFixed(2)}%`
}

function money (v: string | number | null | undefined): string {
  return `${toNum(v).toFixed(2)} 元`
}

export function BacktestSummary ({ data }: BacktestSummaryProps) {
  const equity = data.equity_curve ?? []
  const scoreBands = Object.entries(data.results_by_score ?? {})

  const pieData = scoreBands.map(([name, stats]) => ({
    name,
    value: stats.bets
  }))

  const fixedStake = toNum(data.fixed_stake)
  const initialCapital = toNum(data.initial_capital)
  const totalFixed = fixedStake * data.total_bets
  const pnlFixed = toNum(data.profit_loss)
  const recoveryFixed = totalFixed + pnlFixed
  const pnlKelly = toNum(data.kelly_profit_loss)

  const bets = data.bets_detail ?? []
  const totalKellyStake = bets.reduce((sum, b) => sum + toNum(b.stake_kelly), 0)
  const recoveryKelly = totalKellyStake + pnlKelly

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className={styles.summaryBanner}>
        <span>总场次 <strong>{data.total_bets}</strong></span>
        <span>命中 <strong>{data.hit_count}</strong> 场</span>
        <span>命中率 <strong>{pct(data.hit_rate)}</strong></span>
        <span>初始本金 <strong>{money(initialCapital)}</strong></span>
        <span>每场固定投注 <strong>{money(fixedStake)}</strong></span>
      </div>

      <div className={styles.cardSection}>固定投注模式</div>
      <div className={styles.cardGrid}>
        <Card label="总投入（固定）" value={money(totalFixed)} sub="每场固定投注 × 总场次" />
        <Card label="总回收（固定）" value={money(recoveryFixed)} sub="命中场次的奖金总和（含本金）" />
        <Card
          label="净盈亏（固定）"
          value={money(pnlFixed)}
          sub={`ROI ${pct(data.roi)}`}
          tone={pnlFixed >= 0 ? 'positive' : 'negative'}
        />
      </div>

      <div className={styles.cardSection}>Kelly 模式</div>
      <div className={styles.cardGrid}>
        <Card label="总投入（Kelly）" value={money(totalKellyStake)} sub="各场 Kelly 建议金额累计" />
        <Card label="总回收（Kelly）" value={money(recoveryKelly)} sub="命中场次的奖金总和（含本金）" />
        <Card
          label="净盈亏（Kelly）"
          value={money(pnlKelly)}
          sub={`ROI ${pct(data.kelly_roi)}`}
          tone={pnlKelly >= 0 ? 'positive' : 'negative'}
        />
      </div>

      {equity.length > 0 && (
        <div className={styles.chartWrapper}>
          <div className={styles.chartTitle}>累计盈亏曲线</div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={equity}>
              <CartesianGrid stroke="rgb(51 65 85)" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="cumulative_pnl_fixed"
                name="固定投注"
                stroke="#22d3ee"
                dot={false}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="cumulative_pnl_kelly"
                name="Kelly"
                stroke="#f97316"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {pieData.length > 0 && (
        <div className={styles.chartWrapper}>
          <div className={styles.chartTitle}>分数段分布</div>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Tooltip />
              <Legend />
              <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={90} label>
                {pieData.map((_, idx) => (
                  <Cell key={idx} fill={BAND_COLORS[idx % BAND_COLORS.length]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className={styles.hint}>
        备注：MVP 基于当前抓取的最新一份赔率做回测，历史赔率快照功能将在后续版本引入。
      </div>
    </div>
  )
}

interface CardProps {
  label: string
  value: string
  sub?: string
  tone?: 'positive' | 'negative'
}

function Card ({ label, value, sub, tone }: CardProps) {
  const toneClass = tone === 'positive'
    ? styles.cardPositive
    : tone === 'negative'
      ? styles.cardNegative
      : ''
  return (
    <div className={`${styles.card} ${toneClass}`}>
      <div className={styles.cardLabel}>{label}</div>
      <div className={styles.cardValue}>{value}</div>
      {sub && <div className={styles.cardSub}>{sub}</div>}
    </div>
  )
}
```

- [ ] **Step 3: TypeScript 检查**

```bash
cd frontend && npx tsc --noEmit
```

预期：无错。

- [ ] **Step 4: Commit**

```bash
git add frontend/app/backtest/backtest-summary.tsx frontend/app/backtest/backtest-client.module.css
git commit -m "feat(fe): backtest 概览区改为 6 卡真实金额视图"
```

---

### Task 12: 下注明细表组件

**Files:**
- Create: `frontend/app/backtest/backtest-bets-table.tsx`
- Create: `frontend/app/backtest/backtest-bets-table.module.css`

- [ ] **Step 1: 写 CSS**

`frontend/app/backtest/backtest-bets-table.module.css`：

```css
.wrapper {
  border: 1px solid rgb(51 65 85);
  border-radius: 0.5rem;
  background: rgb(15 23 42 / 0.5);
  padding: 1rem;
  overflow-x: auto;
}

.title {
  font-size: 0.9rem;
  font-weight: 500;
  margin-bottom: 0.5rem;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
  min-width: 900px;
}

.table th,
.table td {
  padding: 0.5rem 0.5rem;
  border-bottom: 1px solid rgb(51 65 85 / 0.6);
  text-align: left;
  white-space: nowrap;
}

.table th {
  color: rgb(148 163 184);
  font-weight: 500;
}

.hit {
  color: rgb(74 222 128);
}

.miss {
  color: rgb(248 113 113);
}

.positive {
  color: rgb(74 222 128);
}

.negative {
  color: rgb(248 113 113);
}

.footerRow td {
  font-weight: 600;
  border-top: 1px solid rgb(71 85 105);
  border-bottom: 0;
}

.empty {
  color: rgb(148 163 184);
  font-size: 0.85rem;
  padding: 0.75rem 0;
}
```

- [ ] **Step 2: 写组件**

`frontend/app/backtest/backtest-bets-table.tsx`：

```tsx
'use client'

import type { BetDetail } from '@/lib/backtest/types'

import { InfoTooltip } from '@/components/info-tooltip/info-tooltip'
import { BET_TYPE_LABEL, TOOLTIPS } from '@/lib/backtest/tooltips'

import styles from './backtest-bets-table.module.css'

interface BacktestBetsTableProps {
  bets: BetDetail[] | null | undefined
}

function toNum (v: string | number | null | undefined): number {
  if (v === null || v === undefined) return 0
  return typeof v === 'string' ? parseFloat(v) : v
}

function money (v: string | number): string {
  return toNum(v).toFixed(2)
}

function signed (v: string | number): string {
  const n = toNum(v)
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}`
}

function formatDate (d: string): string {
  const [, month, day] = d.split('-')
  return `${month}-${day}`
}

export function BacktestBetsTable ({ bets }: BacktestBetsTableProps) {
  if (!bets || bets.length === 0) {
    return (
      <div className={styles.wrapper}>
        <div className={styles.title}>下注明细</div>
        <div className={styles.empty}>历史回测无明细数据，请重新发起一次回测。</div>
      </div>
    )
  }

  const sorted = [...bets].sort((a, b) => b.match_date.localeCompare(a.match_date))

  const totalFixedStake = sorted.reduce((s, b) => s + toNum(b.stake_fixed), 0)
  const totalFixedPnl = sorted.reduce((s, b) => s + toNum(b.pnl_fixed), 0)
  const totalFixedRecovery = totalFixedStake + totalFixedPnl
  const totalKellyStake = sorted.reduce((s, b) => s + toNum(b.stake_kelly), 0)
  const totalKellyPnl = sorted.reduce((s, b) => s + toNum(b.pnl_kelly), 0)

  return (
    <div className={styles.wrapper}>
      <div className={styles.title}>下注明细（{sorted.length} 场）</div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>日期</th>
            <th>联赛</th>
            <th>对阵</th>
            <th>
              推荐<InfoTooltip text={TOOLTIPS.bet_type} />
            </th>
            <th>
              总分<InfoTooltip text={TOOLTIPS.total_score} />
            </th>
            <th>
              赔率<InfoTooltip text={TOOLTIPS.odds} />
            </th>
            <th>固定投注</th>
            <th>
              Kelly 投注<InfoTooltip text={TOOLTIPS.stake_kelly} />
            </th>
            <th>结果</th>
            <th>固定盈亏</th>
            <th>Kelly 盈亏</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((b) => {
            const pnlFixed = toNum(b.pnl_fixed)
            const pnlKelly = toNum(b.pnl_kelly)
            return (
              <tr key={`${b.match_id}-${b.bet_type}`}>
                <td>{formatDate(b.match_date)}</td>
                <td>{b.league}</td>
                <td>{b.home_team} vs {b.away_team}</td>
                <td>{BET_TYPE_LABEL[b.bet_type] ?? b.bet_type}</td>
                <td>{b.total_score}</td>
                <td>{b.odds}</td>
                <td>{money(b.stake_fixed)}</td>
                <td>{money(b.stake_kelly)}</td>
                <td className={b.is_hit ? styles.hit : styles.miss}>
                  {b.home_score}:{b.away_score} {b.is_hit ? '✓' : '✗'}
                </td>
                <td className={pnlFixed >= 0 ? styles.positive : styles.negative}>
                  {signed(b.pnl_fixed)}
                </td>
                <td className={pnlKelly >= 0 ? styles.positive : styles.negative}>
                  {signed(b.pnl_kelly)}
                </td>
              </tr>
            )
          })}
          <tr className={styles.footerRow}>
            <td colSpan={6}>合计</td>
            <td>{money(totalFixedStake)}</td>
            <td>{money(totalKellyStake)}</td>
            <td>回收 {money(totalFixedRecovery)}</td>
            <td className={totalFixedPnl >= 0 ? styles.positive : styles.negative}>
              {signed(totalFixedPnl)}
            </td>
            <td className={totalKellyPnl >= 0 ? styles.positive : styles.negative}>
              {signed(totalKellyPnl)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 3: TypeScript 检查**

```bash
cd frontend && npx tsc --noEmit
```

预期：无错。

- [ ] **Step 4: Commit**

```bash
git add frontend/app/backtest/backtest-bets-table.tsx frontend/app/backtest/backtest-bets-table.module.css
git commit -m "feat(fe): 新增 BacktestBetsTable 明细组件"
```

---

### Task 13: 在 Client 中挂载明细表 + 端到端验证

**Files:**
- Modify: `frontend/app/backtest/backtest-client.tsx`

- [ ] **Step 1: import & 挂载**

在文件顶部 import 新组件：

```tsx
import { BacktestBetsTable } from './backtest-bets-table'
```

把单回测分支的 `<section>...` 块改为：

```tsx
      ) : selected ? (
        <>
          <section>
            <div className={styles.sectionTitle}>
              回测概览 <span className={styles.pill}>#{selected.id}</span>
            </div>
            <BacktestSummary data={selected} />
          </section>
          <section>
            <BacktestBetsTable bets={selected.bets_detail} />
          </section>
        </>
      ) : null}
```

- [ ] **Step 2: TypeScript 检查**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: 启动 docker compose 并跑 E2E**

```bash
cd /Users/wushunxin/wusx/sporttery_10x && docker compose restart backend frontend
```

打开浏览器 `http://localhost:3000/backtest`：

1. 表单里能看到「每场固定投注金额」输入框，默认 100
2. 所有表单术语旁有 `?` 图标，悬停能看到说明
3. 发起一次回测（日期选择最近一个月，`fixed_stake=100`）
4. 概览区显示 6 张卡 + 顶部辅助信息横幅
5. 卡片下方有「下注明细」表格，至少一行数据且包含对阵名与真实金额
6. 表底有合计行

如果步骤 4-6 有任何数字看不懂，查看浏览器 console 报错并修复。

- [ ] **Step 4: 最终 Commit**

```bash
git add frontend/app/backtest/backtest-client.tsx
git commit -m "feat(fe): backtest 客户端挂载下注明细表"
```

---

## 风险与回滚

- **回滚 migration**：`alembic downgrade 0009` 即可移除新列；前端拿到 `fixed_stake=null` 时 `money(null)` = `0.00 元`，不会崩溃但数字失真 → 如果要彻底回滚，需同时 revert Task 2 / Task 3 两次 commit。
- **老回测 bets_detail=null**：前端 `<BacktestBetsTable bets={null} />` 已处理空态，显示占位文字。
- **Alembic revision 冲突**：如果其他分支已有 `0010`，把 revision 改为 `0011` 并更新 `down_revision`。

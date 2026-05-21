# 回测模块「彩民钱袋子」视角改造

**日期**：2026-04-23
**作者**：设计 by brainstorming 流程
**相关页面**：`/backtest`

---

## 背景与目标

当前 `/backtest` 页面对彩民不友好，用户反馈：

1. **资金要素不足**——看不出"真实花了多少钱、赔了多少、挣了多少"
2. **专业术语缺乏提示**——ROI、Kelly、PnL 等概念没有解释
3. **缺少明细**——看不到具体推荐了哪场、怎么下注、最终结果如何

目标是把回测页面从"**聚合指标 + 图表**"升级为"**彩民钱袋子报告**"：看得懂金额、看得到每一笔、看得明白每个词。

---

## 范围

**包含**：

- 表单新增「每场固定投注金额」输入
- 概览卡片从 4 张扩展到 6 张（固定/Kelly 各 3 张真实金额卡）
- 下方新增下注明细表
- 关键术语添加 Tooltip / 小字说明
- 后端持久化每场明细（JSON 快照）

**不包含**：

- 对比模式（`对比模式：关`）本次不改
- 资金曲线图与分数段饼图保留原样
- 历史赔率快照（MVP 依然用当前赔率）
- 老回测数据迁移（新列允许为 NULL）

---

## 详细设计

### 1. 表单改动（`backtest-form.tsx`）

新增字段「每场固定投注金额」，默认 `100`。

表单字段顺序：
1. 起始日期
2. 结束日期
3. 资金模式
4. **每场固定投注金额（元）** ← 新增
5. 初始本金（元）
6. 模型配置 ID（可空）
7. 开始回测

表单字段都带 Tooltip（`?` 图标，悬停气泡）。

### 2. 概览区（`backtest-summary.tsx`）

#### 2.1 辅助信息横幅（顶部单行小字）

```
总场次 15 · 命中 4 场 · 命中率 26.67% · 初始本金 10000 元 · 每场固定投注 100 元
```

#### 2.2 卡片网格：2 行 × 3 列（固定/Kelly 各一行）

**第一行：固定投注模式**

| 卡片 | 主数值 | 副标题（小灰字，始终显示） |
|------|--------|---------------------------|
| 总投入（固定） | `1500.00 元` | 每场固定投注 × 总场次 |
| 总回收（固定） | `1192.93 元` | 命中场次的奖金总和（含本金） |
| 净盈亏（固定） | `-307.07 元` `ROI -20.47%` | 总回收 − 总投入，即真实赚/亏金额 |

**第二行：Kelly 模式**

| 卡片 | 主数值 | 副标题（小灰字） |
|------|--------|-----------------|
| 总投入（Kelly） | `2874.56 元` | 各场 Kelly 建议金额累计 |
| 总回收（Kelly） | `2525.24 元` | 命中场次的奖金总和（含本金） |
| 净盈亏（Kelly） | `-349.32 元` `ROI -3.49%` | Kelly 模式下的真实赚/亏金额 |

**样式**：

- 净盈亏卡片：正值绿色、负值红色
- 主数值用大字号，ROI 百分比作为副标题右侧小字
- 整体卡片保留暗色主题，与现有风格一致

### 3. 下注明细表（`backtest-bets-table.tsx` 新增组件）

放在概览卡片下方、图表上方。

#### 3.1 列设计（11 列）

| 列 | 示例 | Tooltip |
|----|------|---------|
| 日期 | `04-11` | — |
| 联赛 | `K联赛` | — |
| 对阵 | `仁川联 vs 蔚山现代` | — |
| 推荐 | `平局` / `让球平` | 模型建议下注的玩法：平局 = 直接买平；让球平 = 买让球后的平局 |
| 总分 | `103` | 模型 6 维评分合计，满分 120。≥ 84 才会被推荐 |
| 赔率 | `3.12` | 下注玩法对应的真实赔率。下注金额 × 赔率 = 命中时的奖金 |
| 固定投注 | `100.00` | — |
| Kelly 投注 | `202.50` | 凯利公式按评分高低自动分配的下注金额 |
| 结果 | `2:2 ✓` / `1:0 ✗` | 比分 + 命中图标（绿 ✓ / 红 ✗） |
| 固定盈亏 | `+212.00` / `-100.00` | 正值绿 / 负值红 |
| Kelly 盈亏 | `+429.30` / `-202.50` | 正值绿 / 负值红 |

#### 3.2 交互

- 默认按 **日期倒序**（最近的在上）
- 手机端表格横向滚动
- 表底一行 **合计**：`合计投入（固定） / 合计回收（固定） / 净盈亏（固定）`，与卡片数字一致
- 老回测（无 `bets_detail` 字段）显示空状态：`历史回测无明细数据，请重新发起一次回测`

### 4. Tooltip 文案统一入口

前端新建一个 `lib/backtest/tooltips.ts`，导出所有 Tooltip 常量，方便后续修改：

```ts
export const TOOLTIPS = {
  mode: '两者兼顾：同时计算固定和 Kelly 两种策略，便于对比。',
  fixed_stake: '固定模式下每场下注的金额（元）。不管评分高低都下这个数，便于简单评估。',
  initial_capital: 'Kelly 模式下的总资金池，凯利公式按当前本金比例决定每场下注金额。',
  model_config_id: '使用哪套模型规则。留空则用当前激活的模型。',
  bet_type: '模型建议下注的玩法：平局 = 直接买平；让球平 = 买让球后的平局。',
  total_score: '模型 6 维评分合计，满分 120。≥ 84 才会被推荐。',
  odds: '下注玩法对应的真实赔率（澳门欧赔）。下注金额 × 赔率 = 命中时的奖金。',
  stake_kelly: '凯利公式按评分高低自动分配的下注金额。评分越高投注越多。'
}
```

配一个通用 `<InfoTooltip text="..." />` 组件（基于 Radix UI Tooltip），用在表单字段和表头。

---

## 后端改动

### 5. Schema 调整（`app/schemas/backtest.py`）

**BacktestCreate** 新增：

```python
fixed_stake: Decimal = Field(default=Decimal("100"), ge=Decimal("0.01"))
```

**BacktestSummary** 新增：

```python
fixed_stake: Decimal | None = None
bets_detail: list[dict[str, Any]] | None = None
```

### 6. Model 调整（`app/models/backtest.py`）

`BacktestSession` 表新增两列：

```python
fixed_stake: Mapped[Decimal | None] = mapped_column(
    DECIMAL(14, 2), nullable=True, comment="每场固定投注金额(CNY)"
)
bets_detail: Mapped[list[dict[str, Any]] | None] = mapped_column(
    JSON, nullable=True, comment="每场明细 JSON 快照"
)
```

### 7. Alembic Migration

新建 `0010_backtest_stake_and_details.py`：

```python
def upgrade():
    op.add_column('backtest_sessions',
        sa.Column('fixed_stake', sa.DECIMAL(14, 2), nullable=True,
                  comment='每场固定投注金额(CNY)'))
    op.add_column('backtest_sessions',
        sa.Column('bets_detail', sa.JSON, nullable=True,
                  comment='每场明细 JSON 快照'))

def downgrade():
    op.drop_column('backtest_sessions', 'bets_detail')
    op.drop_column('backtest_sessions', 'fixed_stake')
```

### 8. 服务改动（`app/engine/backtest_service.py`）

**关键修改**：

- `run()` 方法签名加入 `fixed_stake: Decimal`
- 循环内 `simulate_bet(stake_fixed=fixed_stake, ...)` 传递真实金额
- `BetOutcome.stake_fixed` 从 `Decimal("1")` 改为传入金额
- 循环结束后构造 `bets_detail` 列表（每项包含所有展示字段）
- `_persist()` 写入 `fixed_stake` 和 `bets_detail`

**bets_detail 结构**：

```json
[
  {
    "match_id": 202604116004,
    "match_date": "2026-04-11",
    "league": "K联赛",
    "home_team": "仁川联",
    "away_team": "蔚山现代",
    "bet_type": "draw",
    "total_score": 103,
    "odds": "3.12",
    "stake_fixed": "100.00",
    "stake_kelly": "202.50",
    "is_hit": true,
    "home_score": 2,
    "away_score": 2,
    "pnl_fixed": "212.00",
    "pnl_kelly": "429.30"
  }
]
```

**注意**：Decimal 序列化为字符串以保留精度，前端渲染时 `parseFloat` 即可。

### 9. API 端点

无新端点。`POST /api/backtest` 接受 `fixed_stake` 参数；`GET /api/backtest/{id}` 返回 `bets_detail`。

---

## 测试策略

### 后端

新增 `tests/test_backtest_service_money.py`：

- **test_fixed_stake_applied**：验证 `fixed_stake=50` 时每场 stake 为 50
- **test_total_staked_computed**：验证 `total_stake_fixed` = `fixed_stake × total_bets`
- **test_bets_detail_shape**：验证 `bets_detail` JSON 包含所有必需字段且数量等于推荐场次
- **test_bets_detail_persisted**：验证 session 重新查询后 `bets_detail` 不丢失
- **test_hit_pnl_correct**：命中场 `pnl_fixed = stake × (odds - 1)`；未命中场 `pnl_fixed = -stake`

### 前端

在现有 Jest 设置下新增：

- `backtest-summary.test.tsx`：渲染 mock 数据，验证 6 张卡片金额正确（包括正负颜色）
- `backtest-bets-table.test.tsx`：mock `bets_detail`，验证：
  - 表格渲染全部行
  - 命中行显示 ✓，未命中行显示 ✗
  - 盈亏颜色正确（正值绿、负值红）
  - 老回测（`bets_detail = null`）显示空状态

### 端到端验证

Playwright 流程：

1. 发起一次回测（`fixed_stake=100`）
2. 验证 6 张卡片数值
3. 验证明细表行数等于 `total_bets`
4. 验证表底合计与卡片数字一致

---

## 风险与权衡

### 风险 1：JSON 字段性能

`bets_detail` 存 JSON，单次回测最多 90 天，按一个月 15 场估算约 45 场，JSON 不超过 10 KB。MVP 规模无性能问题。

### 风险 2：老回测显示空

旧的 `#1` 回测 `bets_detail = NULL`。前端检测到空即显示"历史回测无明细数据"的占位，不做数据迁移。

### 风险 3：向后兼容

- `BacktestCreate.fixed_stake` 有默认值（100），旧客户端不传也可以
- `BacktestSummary.fixed_stake` 和 `bets_detail` 为可空，旧记录不报错

---

## 实施顺序

1. **后端改动**（可独立合并）
   - Migration 0010
   - Model 增加字段
   - Schema 增加字段
   - `BacktestService.run` 支持 `fixed_stake` + 构造 `bets_detail`
   - 新增单元测试
2. **前端类型同步**
   - 更新 `lib/backtest/types.ts`
3. **前端 UI 改动**
   - `<InfoTooltip />` 通用组件
   - `tooltips.ts` 文案集中管理
   - 表单增加 `fixed_stake` 字段
   - `BacktestSummary` 扩展为 6 卡
   - 新增 `<BacktestBetsTable />` 组件并挂载到 `backtest-client.tsx`
4. **端到端测试**
   - 跑一次真实回测，截图验证

---

## 成功标准

- 彩民打开 `/backtest` 页面，能在 3 秒内回答：
  1. 这次回测一共花了多少钱？
  2. 赢了多少钱？
  3. 净赚/净亏多少？
- 任何专业术语旁都有解释，新手也能看懂
- 能逐场查看每场推荐的金额、结果、盈亏

# V3.4 二串一组单选择器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 V3.2 单场候选池不变的前提下，实现 V3.4 二串一组单选择器，回测 balanced/conservative/frequency 三种策略，并与全市场随机、候选池随机和同频约束随机对照。

**Architecture:** 复用 V3.3 `backend/app/research` 基础设施，新增 `combo_selector.py` 负责 pair scoring 和策略生成，新增 `v34_combo_selector.py` CLI 生成报告并写入 `model_research_runs`。前端无需新增页面，只复用最新研究摘要 API。

**Tech Stack:** Python + SQLAlchemy + pytest + ruff；已有 MySQL 研究表；Next.js 页面复用 `/api/research/latest`。

---

## Task 1: 组单选择器纯函数

**Files:**
- Create: `backend/app/research/combo_selector.py`
- Test: `backend/tests/test_research_combo_selector.py`

步骤:

1. 写测试：验证组合赔率区间过滤、同联赛惩罚、balanced 优先选择不同联赛且赔率区间合格的 pair。
2. 实现 `score_pair(a, b, profile)`。
3. 实现 `select_combo_tickets(candidates, strategy)`。
4. 运行 `pytest tests/test_research_combo_selector.py -q`。

## Task 2: V3.4 CLI 和报告

**Files:**
- Create: `backend/app/scripts/v34_combo_selector.py`
- Modify: `backend/app/research/reporting.py` if reusable helpers are needed
- Test: `backend/tests/test_research_combo_selector.py`

步骤:

1. CLI 参数：`--start --end --model --random-trials --random-seed --replace --report`。
2. 加载 V3.2 候选和全市场候选。
3. 生成 balanced/conservative/frequency 三种策略。
4. 为每种策略生成随机对照。
5. 写 Markdown、tickets CSV、random CSV。
6. 写入 `model_research_runs.name = v34-combo-selector`。

## Task 3: 生成报告和更新索引

**Files:**
- Generate: `docs/analysis/2026-04-26-v34-combo-selector-backtest.md`
- Generate: `docs/analysis/v34-combo-selector-tickets.csv`
- Generate: `docs/analysis/v34-combo-selector-random.csv`
- Modify: `docs/analysis/MODEL_RESEARCH_INDEX.md`

步骤:

1. 运行 V3.4 CLI。
2. 查询 DB 确认 research run 和 artifact。
3. 更新模型研究索引。
4. 浏览器确认 `/backtest` 显示最新 V3.4 研究摘要。

## Task 4: 验证

命令:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_metrics.py tests/test_research_combo.py tests/test_research_random_baseline.py tests/test_research_combo_selector.py -q
cd backend && .venv/bin/python -m ruff check app/research app/scripts/v34_combo_selector.py tests/test_research_combo_selector.py
cd frontend && pnpm test -- research-api.test.ts research-summary.test.tsx backtest-client.test.tsx
```

验收:

1. 测试全部通过。
2. ruff 通过。
3. 页面显示 V3.4。
4. 报告如实写明是否跑赢约束随机。

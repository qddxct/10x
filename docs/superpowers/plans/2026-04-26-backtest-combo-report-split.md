# 回测与二串一报告页面拆分实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将历史回测页面和二串一测试报告页面拆成两个独立入口，避免 `/backtest` 混杂组合报告。

**Architecture:** `/backtest` 只保留回测功能；新增 `/combo-reports` 加载最新研究报告；迁移明细页到 `/combo-reports/[runId]`；旧 `/backtest/research/[runId]` 做路由跳转。

**Tech Stack:** Next.js App Router, React, TypeScript, Vitest, Testing Library。

---

## Task 1: 回测页去除研究报告依赖

**Files:**
- Modify: `frontend/app/backtest/backtest-client.tsx`
- Modify: `frontend/tests/backtest-client.test.tsx`

- [ ] 写失败测试：`BacktestClient` 不调用 `getLatestResearchRun()`，不显示 `研究报告` 卡片。
- [ ] 删除 `BacktestClient` 中研究报告 state、effect、import 和渲染。
- [ ] 在页头增加跳转 `/combo-reports` 的轻量入口。
- [ ] 运行 `frontend/tests/backtest-client.test.tsx`。

## Task 2: 新增二串一报告入口页

**Files:**
- Create: `frontend/app/combo-reports/page.tsx`
- Create: `frontend/app/combo-reports/combo-reports-client.tsx`
- Create: `frontend/app/combo-reports/combo-reports.module.css`
- Move/Modify: `frontend/app/backtest/research-summary.tsx` 或新建 `frontend/app/combo-reports/research-summary.tsx`
- Modify: `frontend/tests/research-summary.test.tsx`
- Create: `frontend/tests/combo-reports-client.test.tsx`

- [ ] 写失败测试：有最新报告时 `/combo-reports` 客户端展示摘要和明细链接。
- [ ] 写失败测试：无报告时展示空状态。
- [ ] 新增 `ComboReportsClient`，调用 `getLatestResearchRun()`。
- [ ] 调整 `ResearchSummary` 明细链接到 `/combo-reports/[id]`。
- [ ] 运行报告入口相关测试。

## Task 3: 迁移报告明细页

**Files:**
- Create/Move: `frontend/app/combo-reports/[runId]/page.tsx`
- Create/Move: `frontend/app/combo-reports/[runId]/research-detail-client.tsx`
- Create/Move: `frontend/app/combo-reports/[runId]/research-detail.module.css`
- Modify: `frontend/app/backtest/research/[runId]/page.tsx`
- Modify: `frontend/tests/research-detail-client.test.tsx`

- [ ] 写失败测试：明细客户端导入新路径，返回链接指向 `/combo-reports`。
- [ ] 迁移页面和样式。
- [ ] 将旧路径改为 `redirect('/combo-reports/[runId]')`。
- [ ] 运行明细页测试。

## Task 4: 总体验证

**Run:**

```bash
cd frontend && npm test -- backtest-client research-summary combo-reports-client research-detail-client
cd frontend && npm run lint
```

如果项目没有对应脚本或脚本不可用，记录实际可运行的替代命令和结果。

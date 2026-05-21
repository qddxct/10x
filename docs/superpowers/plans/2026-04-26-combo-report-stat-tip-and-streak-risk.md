# 二串一报告统计提示与连中连不中风险实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在二串一报告明细页中解释随机对照统计概念，并展示每个方案的最大连中、最大连不中风险。

**Architecture:** 后端在 ticket-groups 聚合层根据逐票命中序列计算 streak 指标；前端展示统计口径说明和分组 streak 摘要；不改变模型脚本和选号逻辑。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Next.js, React, TypeScript, pytest, Vitest。

---

## Task 1: 后端 ticket-groups 返回 streak 指标

**Files:**
- Modify: `backend/app/research/repository.py`
- Modify: `backend/app/schemas/research.py`
- Modify: `backend/tests/test_research_api.py`

- [x] 在 API 测试中断言 `max_hit_streak` 和 `max_miss_streak`。
- [x] 在 repository 中按 tickets 顺序计算最大连中和最大连不中。
- [x] 扩展 Pydantic summary schema。
- [x] 运行 `cd backend && .venv/bin/python -m pytest tests/test_research_api.py -q`。

## Task 2: 前端展示统计口径说明和 streak 指标

**Files:**
- Modify: `frontend/lib/research/types.ts`
- Modify: `frontend/app/combo-reports/[runId]/research-detail-client.tsx`
- Modify: `frontend/app/combo-reports/[runId]/research-detail.module.css`
- Modify: `frontend/tests/research-detail-client.test.tsx`

- [x] 在组件测试中断言 `统计口径说明`、`P90`、`模型分位`、`最大连不中` 解释。
- [x] 在组件测试中断言每个分组摘要展示 `最大连中` 和 `最大连不中`。
- [x] 扩展前端类型。
- [x] 增加提示卡片和分组 streak 文案。
- [x] 运行 `cd frontend && npm test -- research-detail-client && npm run lint`。

## Task 3: 浏览器验证

- [x] 重建前端容器。
- [x] 用浏览器打开 `/combo-reports/8`。
- [x] 验证随机对照区能看到统计口径说明。
- [x] 验证二串一逐票明细分组摘要能看到最大连中和最大连不中。

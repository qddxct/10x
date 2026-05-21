# 二串一报告对照组明细实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在二串一报告明细页中同时展示模型方案和两个随机对照组的逐票明细。

**Architecture:** 研究脚本生成 `random_ticket` 产物；后端新增 `ticket-groups` 聚合 API；前端明细页改为按组展示票据。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Python research scripts, Next.js, React, TypeScript, Vitest, pytest。

---

## Task 1: 保存随机对照逐票产物

**Files:**
- Modify: `backend/app/research/random_baseline.py`
- Modify: `backend/app/scripts/v34_combo_selector.py`
- Modify: `backend/tests/test_research_random_baseline.py`
- Modify: `backend/tests/test_research_combo_selector.py`

- [x] 写失败测试：固定 seed 能生成稳定数量的随机票。
- [x] 新增函数 `sample_random_combo_tickets()`。
- [x] V3.4 脚本为两个随机对照组保存 `random_ticket` artifacts。
- [x] 测试随机票 payload 包含 `group_type` 和 `control_label`。

## Task 2: 新增 ticket-groups API

**Files:**
- Modify: `backend/app/research/repository.py`
- Modify: `backend/app/api/research.py`
- Modify: `backend/app/schemas/research.py`
- Modify: `backend/tests/test_research_api.py`

- [x] 写失败测试：`/api/research/{run_id}/ticket-groups` 返回模型组和随机组。
- [x] 新增聚合函数读取 `combo_ticket` 和 `random_ticket`。
- [x] 新增 Pydantic schema。
- [x] API 返回组标题、说明、金额汇总、tickets。

## Task 3: 前端按组展示明细

**Files:**
- Modify: `frontend/lib/research/api.ts`
- Modify: `frontend/lib/research/types.ts`
- Modify: `frontend/app/combo-reports/[runId]/page.tsx`
- Modify: `frontend/app/combo-reports/[runId]/research-detail-client.tsx`
- Modify: `frontend/tests/research-detail-client.test.tsx`

- [x] 写失败测试：页面展示三组明细标题。
- [x] 新增 `getResearchTicketGroups()`。
- [x] 页面加载 ticket groups。
- [x] 客户端按组渲染明细和金额摘要。

## Task 4: 重新生成当前 V3.4 报告并验证

**Run:**

```bash
cd backend && MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308 MYSQL_DATABASE=sporttery_10x MYSQL_USER=sporttery MYSQL_PASSWORD=sporttery_pass .venv/bin/alembic upgrade head
MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308 MYSQL_DATABASE=sporttery_10x MYSQL_USER=sporttery MYSQL_PASSWORD=sporttery_pass PYTHONPATH=backend backend/.venv/bin/python -m app.scripts.v34_combo_selector --start 2024-09-28 --end 2026-04-22 --model empirical-v32-filtered-candidate --replace
```

- [x] 已对当前报告 `#8` 补写两个随机对照组的 `random_ticket` 明细，两个对照组各 139 张，共 278 条。
- [x] 已重新 build 后端和前端容器。
- [x] 已用浏览器验证 `/combo-reports/8` 展示模型组、全市场随机组、候选池约束随机组三组明细。
